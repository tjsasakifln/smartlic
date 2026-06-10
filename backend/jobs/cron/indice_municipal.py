"""STORY-435 AC7: Cron job trimestral — recálculo do Índice Municipal de Transparência.

CRON-001 (#1630): Heavy IBGE index computation (~15s) offloaded to thread pool
via asyncio.to_thread() to prevent event loop blocking. Uses
_run_with_budget (30s) for timeout safety.
"""

import asyncio
import logging
import os
import time as _time
from datetime import datetime, timezone

from pipeline.budget import _run_with_budget

logger = logging.getLogger(__name__)

# Intervalo aproximado de 90 dias (1 trimestre)
INDICE_MUNICIPAL_INTERVAL = 90 * 24 * 60 * 60  # segundos

# Budget do recálculo (30s — cabe confortavelmente no Railway 120s)
_INDICE_MUNICIPAL_BUDGET_S = 30.0

# Import da métrica de duração (no-op se prometheus_client ausente — gerido por metrics.py)
try:
    from metrics import INDICE_MUNICIPAL_DURATION
except ImportError:
    from metrics import _NoopMetric as _INDICE_MUNICIPAL_DURATION  # type: ignore[assignment]
    INDICE_MUNICIPAL_DURATION = _INDICE_MUNICIPAL_DURATION


def _current_quarter_label() -> str:
    """Retorna o rótulo do trimestre corrente: ex '2026-Q2'."""
    now = datetime.now(timezone.utc)
    q = (now.month - 1) // 3 + 1
    return f"{now.year}-Q{q}"


def _sync_recalcular_municipios(periodo: str) -> dict:
    """Sync wrapper que roda recalcular_municipios_existentes em thread pool.

    CRON-001 (#1630): asyncio.to_thread executa esta função em um worker
    do ThreadPoolExecutor, impedindo que o cálculo pesado (~15s) bloqueie
    o event loop principal e degrade SSE / health checks.
    """
    from services.indice_municipal import recalcular_municipios_existentes
    _loop = asyncio.new_event_loop()
    asyncio.set_event_loop(_loop)
    try:
        return _loop.run_until_complete(recalcular_municipios_existentes(periodo))
    finally:
        _loop.close()


async def run_indice_municipal_recalc() -> dict:
    """Executa o recálculo trimestral do Índice Municipal.

    CRON-001 (#1630): O cálculo é offloadado para thread pool via
    asyncio.to_thread e protegido por _run_with_budget (30s).

    Nunca lança exceção — erros são capturados e retornados no dict.
    """
    periodo = _current_quarter_label()
    start = _time.monotonic()

    try:
        logger.info(
            "STORY-435: iniciando recálculo indice_municipal período %s (thread pool, budget=%.0fs)",
            periodo, _INDICE_MUNICIPAL_BUDGET_S,
        )

        result = await _run_with_budget(
            asyncio.to_thread(_sync_recalcular_municipios, periodo),
            budget=_INDICE_MUNICIPAL_BUDGET_S,
            phase="indice_municipal",
            source="quarterly",
        )

        duration = _time.monotonic() - start
        INDICE_MUNICIPAL_DURATION.observe(duration)

        logger.info(
            "STORY-435: recálculo indice_municipal concluído em %.2fs — %s",
            duration, result,
        )

        # Email summary para admin (falhas de email não abortam o job)
        try:
            from email_service import send_email_async

            admin_email = os.getenv("ADMIN_EMAIL", "tiago.sasaki@gmail.com")
            body_lines = [f"<p>Índice Municipal recalculado para <strong>{periodo}</strong>.</p><ul>"]
            for k, v in result.items():
                body_lines.append(f"<li><strong>{k}</strong>: {v}</li>")
            body_lines.append("</ul>")
            body = "\n".join(body_lines)

            await send_email_async(
                admin_email,
                f"[SmartLic] Índice Municipal {periodo} — recálculo trimestral",
                body,
            )
            logger.info("STORY-435: email summary enviado para %s", admin_email)
        except Exception as email_err:
            logger.warning("STORY-435: falha ao enviar email summary: %s", email_err)

        return result

    except asyncio.TimeoutError:
        logger.error(
            "STORY-435: recálculo indice_municipal excedeu budget de %.0fs",
            _INDICE_MUNICIPAL_BUDGET_S,
        )
        return {"status": "error", "error": f"timeout: budget de {_INDICE_MUNICIPAL_BUDGET_S}s excedido"}

    except Exception as exc:
        logger.error("STORY-435: recálculo indice_municipal falhou: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}


async def _indice_municipal_loop() -> None:
    """Loop de background: aguarda 120s no startup, depois recalcula a cada 90 dias.

    O delay inicial evita que o recálculo bloqueie o event loop durante o startup,
    o que causava timeout no healthcheck do Railway (GET /health/live > 120s).
    """
    # Delay inicial para não competir com healthcheck de startup
    await asyncio.sleep(120)
    while True:
        try:
            await run_indice_municipal_recalc()
        except asyncio.CancelledError:
            logger.info("STORY-435: indice_municipal task cancelada")
            break
        except Exception as e:
            logger.error("STORY-435: erro inesperado no loop indice_municipal: %s", e, exc_info=True)
        await asyncio.sleep(INDICE_MUNICIPAL_INTERVAL)


async def start_indice_municipal_task() -> asyncio.Task:
    """Cria e retorna a asyncio.Task do loop trimestral."""
    task = asyncio.create_task(
        _indice_municipal_loop(), name="indice_municipal_quarterly"
    )
    logger.info("STORY-435: indice_municipal quarterly recalc task started (interval=90d)")
    return task
