"""TEST-ERR-RECOVERY-2026-001 AC3.2 — OpenAI down → fallback summary.

Validates the contract enforced in ``backend/jobs/queue/jobs.py::llm_summary_job``:
when ``get_or_generate_resumo_cached`` raises (HTTP 503, network error,
parse error from OpenAI), the job catches the exception and falls back
to ``gerar_resumo_fallback`` (deterministic, no LLM). The user always
gets a summary — the search pipeline NEVER 500s because of OpenAI.

Origin: 2026-04 LLM outage — OpenAI returned 503 for ~15 minutes;
the existing try/except + fallback was the only thing keeping the
search pipeline alive. SDD trace: ``llm_summary_job`` lines 426–436.
"""

from __future__ import annotations

from unittest.mock import patch, AsyncMock, MagicMock

import pytest


def _sample_bid(uf: str = "SC") -> dict:
    return {
        "numero_controle_pncp": f"abc-{uf}",
        "uf": uf,
        "uf_label": uf,
        "objeto": "Pavimentação asfáltica",
        "objetoCompra": "Pavimentação asfáltica",
        "valorTotalEstimado": 100000.0,
        "valor_estimado": 100000.0,
        "data_publicacao": "2026-05-01",
        "dataAberturaProposta": "2026-05-15T10:00:00",
        "modalidade": "pregao",
        "orgao": "Prefeitura de Teste",
        "nomeOrgao": "Prefeitura de Teste",
    }


@pytest.mark.asyncio
async def test_openai_503_falls_back_to_deterministic_summary():
    """AC3.2.a — When the cached LLM helper raises, fallback is invoked."""
    from jobs.queue import jobs as jobs_mod

    licitacoes = [_sample_bid("SC"), _sample_bid("PR")]

    # Mock the tracker so the SSE emit path is a no-op.
    tracker = MagicMock()
    tracker.emit = AsyncMock()

    # Mock persist_job_result so we don't need a result store backend.
    with patch("llm.get_or_generate_resumo_cached",
               new_callable=AsyncMock,
               side_effect=RuntimeError("openai 503 service unavailable")), \
         patch("jobs.queue.result_store.persist_job_result", new_callable=AsyncMock), \
         patch("progress.get_tracker", new_callable=AsyncMock,
               return_value=tracker):

        result = await jobs_mod.llm_summary_job(
            ctx={},
            search_id="search-recovery-001",
            licitacoes=licitacoes,
            sector_name="construcao",
            termos_busca="asfalto",
        )

    # Contract: returns a dict (model_dump output), never raises.
    assert isinstance(result, dict)
    assert result.get("total_oportunidades") == 2
    # SSE event must have fired so the frontend can render the placeholder.
    tracker.emit.assert_awaited_once()
    args = tracker.emit.await_args.args
    assert args[0] == "llm_ready"


@pytest.mark.asyncio
async def test_openai_timeout_falls_back():
    """AC3.2.b — Edge: TimeoutError is also caught (not just generic Exception)."""
    import asyncio
    from jobs.queue import jobs as jobs_mod

    tracker = MagicMock()
    tracker.emit = AsyncMock()

    with patch("llm.get_or_generate_resumo_cached",
               new_callable=AsyncMock,
               side_effect=asyncio.TimeoutError("openai timeout")), \
         patch("jobs.queue.result_store.persist_job_result", new_callable=AsyncMock), \
         patch("progress.get_tracker", new_callable=AsyncMock,
               return_value=tracker):

        result = await jobs_mod.llm_summary_job(
            ctx={},
            search_id="search-recovery-002",
            licitacoes=[_sample_bid("MG")],
            sector_name="ti",
        )

    assert isinstance(result, dict)
    assert result.get("total_oportunidades") == 1


def test_fallback_helper_handles_empty_input():
    """AC3.2.c — ``gerar_resumo_fallback`` is safe for the 0-bid edge."""
    import llm
    out = llm.gerar_resumo_fallback([], sector_name="construcao")
    assert out is not None
    assert out.total_oportunidades == 0
    assert out.valor_total == 0.0


def test_fallback_helper_handles_partial_data():
    """AC3.2.d — Sparse fields must not raise (deterministic logic only)."""
    import llm
    sparse = {"numero_controle_pncp": "x", "uf": "SC"}  # nearly empty
    out = llm.gerar_resumo_fallback([sparse], sector_name="construcao")
    assert out is not None
    assert out.total_oportunidades == 1
