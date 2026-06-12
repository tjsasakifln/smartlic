"""NETINT-005: Fire-and-forget event collection for network intelligence.

Singleton service that exposes ``collect_event()`` for recording anonymized
network analytics events (search_query, sector_view, org_view, cnpj_lookup).

Flow:
1. Check ``profiles.allow_network_analytics`` for the current user.
2. If opt-out → discard silently.
3. Sanitize metadata via ``utils.event_sanitizer.sanitize_metadata``.
4. Fire-and-forget call to RPC ``network_record_event`` via Supabase admin client.
5. Increment Prometheus counter ``smartlic_network_events_collected_total``.

Usage::

    from services.network_collector import collect_event

    await collect_event(
        user_id="...",
        evento_tipo="sector_view",
        dimensao_tipo="setor",
        dimensao_valor="saude",
        metadados={"source": "observatorio"},
    )
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from database import get_db
from supabase_client import sb_execute
from utils.event_sanitizer import sanitize_metadata

logger = logging.getLogger(__name__)

# Fire-and-forget timeout — never block the caller for more than 2s.
_COLLECT_TIMEOUT_S = 2.0


async def _get_opt_in(user_id: str) -> bool | None:
    """Check if the user has opted into network analytics collection.

    Returns:
        ``True`` if opted in, ``False`` if opted out, ``None`` if
        the profile lookup failed (treat as opt-out).
    """
    try:
        result = await sb_execute(
            get_db()
            .table("profiles")
            .select("allow_network_analytics")
            .eq("id", user_id)
            .limit(1)
            .single()
        )
    except Exception as e:
        logger.debug("network_collector: profile lookup failed for user %s: %s", user_id[:8], e)
        return None

    if result.data is None:
        return None

    val = result.data.get("allow_network_analytics")
    return True if val is True else False


async def collect_event(
    user_id: str,
    evento_tipo: str,
    dimensao_tipo: str,
    dimensao_valor: str,
    metadados: dict[str, Any] | None = None,
) -> bool:
    """Record an anonymized network analytics event (fire-and-forget).

    Args:
        user_id: The authenticated user's ID (used only for opt-in check).
        evento_tipo: Event type (search_query, sector_view, org_view, cnpj_lookup).
        dimensao_tipo: Dimension type (setor, uf, modalidade, orgao).
        dimensao_valor: Dimension value (e.g. saude, SP, pregao).
        metadados: Optional metadata dict (will be sanitized before storage).

    Returns:
        ``True`` if the event was collected (or silently discarded due to
        opt-out). ``False`` if the collection failed (logged, not raised).
    """
    # ── Step 1: Opt-in check ─────────────────────────────────────────────
    opt_in = await _get_opt_in(user_id)
    if opt_in is not True:
        logger.debug(
            "network_collector: user %s opt-in=%s — event discarded",
            user_id[:8], opt_in,
        )
        return True  # Silent discard — never reveal opt-out status

    # ── Step 2: Sanitize metadata ──────────────────────────────────────────
    clean_metadados = sanitize_metadata(metadados or {})

    # ── Step 3: Fire-and-forget RPC call ───────────────────────────────────
    try:
        await asyncio.wait_for(
            sb_execute(
                get_db().rpc("network_record_event", {
                    "p_evento_tipo": evento_tipo,
                    "p_dimensao_tipo": dimensao_tipo,
                    "p_dimensao_valor": dimensao_valor,
                    "p_metadados": clean_metadados,
                }),
                category="rpc",
            ),
            timeout=_COLLECT_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "network_collector: RPC call timed out after %ss for event %s/%s/%s",
            _COLLECT_TIMEOUT_S, evento_tipo, dimensao_tipo, dimensao_valor,
        )
        _increment_metric(evento_tipo, status="timeout")
        return False
    except Exception as e:
        logger.warning(
            "network_collector: RPC call failed for event %s/%s/%s: %s",
            evento_tipo, dimensao_tipo, dimensao_valor, e,
        )
        _increment_metric(evento_tipo, status="error")
        return False

    # ── Step 4: Metrics ───────────────────────────────────────────────────
    _increment_metric(evento_tipo, status="success")
    logger.debug(
        "network_collector: event recorded %s/%s/%s",
        evento_tipo, dimensao_tipo, dimensao_valor,
    )
    return True


def _increment_metric(evento_tipo: str, status: str) -> None:
    """Increment the collection counter (best-effort, no-op if metrics off)."""
    try:
        from metrics import NETWORK_EVENTS_COLLECTED_TOTAL
        NETWORK_EVENTS_COLLECTED_TOTAL.labels(
            evento_tipo=evento_tipo, status=status,
        ).inc()
    except Exception:
        pass  # Metrics best-effort
