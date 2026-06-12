"""SUBINTEL-011 (#1674): Partnership Score route.

GET /v1/subcontract/partnership-score/{cnpj} — returns partnership opportunity score
for a given supplier CNPJ based on subcontract_capacity_signals RPC.

Feature flag: SUBCONTRACT_INTEL_ENABLED (config/features.py)
Plan capability: allow_subcontract_intel (gate: requires_subcontract_intel)
"""

from __future__ import annotations

import logging
import time
from fastapi import APIRouter, Depends, HTTPException, Path, Request

from quota.plan_auth import get_subcontract_intel_dependency

from schemas.subcontract_intel import (
    CapacitySignals,
    PartnershipScoreResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["subcontract_intel"])

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 3600  # 1h — signals change slowly
_partnership_cache: dict[str, tuple[dict, float]] = {}


def _get_cached(key: str) -> dict | None:
    if key not in _partnership_cache:
        return None
    data, ts = _partnership_cache[key]
    if time.time() - ts >= _CACHE_TTL_SECONDS:
        del _partnership_cache[key]
        return None
    return data


def _set_cached(key: str, data: dict) -> None:
    _partnership_cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# LLM Narrative prompt (SUBINTEL-011 v1 — premium only)
# ---------------------------------------------------------------------------
_SUBCONTRACT_OPPORTUNITY_PROMPT = """You are a B2G (Business-to-Government) intelligence analyst.

Given the following partnership signals for a Brazilian supplier, write ONE short
paragraph (2-3 sentences) explaining why their Partnership Score is {score:.0%} and
what types of partnership or subcontracting opportunities make sense.

Supplier: {razao_social}
CNPJ: {cnpj}

Signals:
- Repeat Winner Score: {repeat_score:.2f} ({repeat_label})
- Large Contract Score: {large_score:.2f} ({large_label})
- Subcontracting Pattern Score: {sub_score:.2f} ({sub_label})

Respond in Brazilian Portuguese. Be specific and actionable. Do not use markdown."""


def _compute_signal_label(score: float) -> str:
    """Map a 0.0-1.0 score to a human label."""
    if score >= 0.7:
        return "Alto"
    if score >= 0.4:
        return "Medio"
    return "Baixo"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_DISCLAIMER = (
    "Score estimado com base em contratos públicos disponiveis em fontes oficiais "
    "(PNCP, PCP, ComprasGov). Este score e uma indicacao de capacidade operacional "
    "e nao constitui recomendacao de investimento ou parceria comercial."
)


def _compute_scores(rpc_data: dict) -> dict:
    """Convert RPC data into PartnershipScore signal structure.

    Computes three signal scores from the RPC return shape:
      repeat_winner: based on total_contratos + contratos_por_ano distribution
      large_contract: based on ticket_medio relative to 500k threshold
      subcontracting_pattern: based on contratos_simultaneos_pico + ufs_distintas
    """
    total = rpc_data.get("total_contratos", 0) or 0
    valor_total = rpc_data.get("valor_total", 0) or 0
    ticket_medio = rpc_data.get("ticket_medio", 0) or 0
    pico = rpc_data.get("contratos_simultaneos_pico", 0) or 0
    ufs = rpc_data.get("ufs_distintas", 0) or 0
    orgaos = rpc_data.get("orgaos_distintas", 0) or 0
    score_capacidade = rpc_data.get("score_capacidade", 0) or 0

    # repeat_winner: capacity score + contract volume signal
    repeat_score = min(1.0, score_capacidade * 0.6 + min(1.0, total / 100) * 0.4)

    # large_contract: ticket_medio relative to threshold
    large_score = min(1.0, ticket_medio / 500_000)

    # subcontracting_pattern: multi-orgao + multi-UF + concurrent contracts
    sub_score = min(
        1.0,
        min(1.0, orgaos / 20) * 0.35
        + min(1.0, ufs / 10) * 0.35
        + min(1.0, pico / 15) * 0.30,
    )

    return {
        "repeat_winner": {
            "score": round(repeat_score, 2),
            "label": _compute_signal_label(repeat_score),
            "description": f"Capacidade de vencer contratos recorrentemente. {total} contratos, valor total de R$ {valor_total:,.2f}.",
            "details": {
                "total_contratos": total,
                "valor_total": valor_total,
                "score_capacidade_rpc": score_capacidade,
            },
        },
        "large_contract": {
            "score": round(large_score, 2),
            "label": _compute_signal_label(large_score),
            "description": f"Capacidade de executar contratos de grande porte. Ticket medio de R$ {ticket_medio:,.2f}.",
            "details": {
                "ticket_medio": ticket_medio,
                "threshold_referencia": 500_000,
            },
        },
        "subcontracting_pattern": {
            "score": round(sub_score, 2),
            "label": _compute_signal_label(sub_score),
            "description": f"Padrao de atuacao com multiplos orgaos. Atua em {ufs} UFs com {orgaos} orgaos distintos.",
            "details": {
                "ufs_distintas": ufs,
                "orgaos_distintos": orgaos,
                "contratos_simultaneos_pico": pico,
            },
        },
    }


async def _generate_narrative(
    scores: dict,
    cnpj: str,
    razao_social: str,
) -> str | None:
    """Generate LLM narrative for premium users.

    Returns None on failure (graceful degradation).
    """
    try:
        from llm import generate_narrative as llm_generate

        overall = (
            scores["repeat_winner"]["score"] * 0.35
            + scores["large_contract"]["score"] * 0.30
            + scores["subcontracting_pattern"]["score"] * 0.35
        )

        prompt = _SUBCONTRACT_OPPORTUNITY_PROMPT.format(
            score=overall,
            razao_social=razao_social,
            cnpj=cnpj,
            repeat_score=scores["repeat_winner"]["score"],
            repeat_label=scores["repeat_winner"]["label"],
            large_score=scores["large_contract"]["score"],
            large_label=scores["large_contract"]["label"],
            sub_score=scores["subcontracting_pattern"]["score"],
            sub_label=scores["subcontracting_pattern"]["label"],
        )

        narrative = await llm_generate(prompt, max_tokens=200)
        return narrative.strip() if narrative else None
    except Exception as e:
        logger.warning("LLM narrative generation failed for %s: %s", cnpj, e)
        return None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/subcontract/partnership-score/{cnpj}",
    summary="Partnership Opportunity Score — avalia fornecedor como potencial parceiro (SUBINTEL-011)",
    response_model=PartnershipScoreResponse,
)
async def get_partnership_score(
    request: Request,
    cnpj: str = Path(..., description="CNPJ do fornecedor (14 digitos)"),
    user: dict = Depends(get_subcontract_intel_dependency()),
):
    """Return partnership opportunity score for the given CNPJ supplier.

    Computes the score from the subcontract_capacity_signals RPC and returns
    three signal dimensions plus an optional LLM-generated narrative for
    premium users.
    """
    # Validate CNPJ format
    if not cnpj or not cnpj.isdigit() or len(cnpj) != 14:
        raise HTTPException(
            status_code=422,
            detail="CNPJ invalido. Deve conter exatamente 14 digitos numericos.",
        )

    cache_key = f"partnership:{cnpj}"
    cached = _get_cached(cache_key)
    if cached:
        return PartnershipScoreResponse(**cached)

    # Fetch RPC data
    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        rpc_result = await sb_execute(
            sb.rpc("subcontract_capacity_signals", {
                "p_ni_fornecedor": cnpj,
                "p_window_months": 24,
            })
        )
        rpc_data = rpc_result.data[0] if rpc_result.data else {}
    except Exception as e:
        logger.error("RPC failed for cnpj=%s: %s", cnpj, e)
        raise HTTPException(status_code=502, detail="Falha ao consultar dados de capacidade.")

    # Compute scores
    scores = _compute_scores(rpc_data)

    # Overall score: weighted average of the three signals
    overall_score = round(
        scores["repeat_winner"]["score"] * 0.35
        + scores["large_contract"]["score"] * 0.30
        + scores["subcontracting_pattern"]["score"] * 0.35,
        2,
    )

    # Get razao_social from RPC or user
    razao_social = rpc_data.get("nome_fornecedor") or f"Fornecedor {cnpj[:8]}"

    # Generate narrative for premium users (optional — graceful degradation)
    narrative = await _generate_narrative(scores, cnpj, razao_social)

    response_dict = {
        "cnpj": cnpj,
        "razao_social": razao_social,
        "overall_score": overall_score,
        "signals": CapacitySignals(**scores),
        "narrative": narrative,
        "disclaimer": _DISCLAIMER,
    }

    _set_cached(cache_key, {
        "cnpj": cnpj,
        "razao_social": razao_social,
        "overall_score": overall_score,
        "signals": scores,
        "narrative": narrative,
        "disclaimer": _DISCLAIMER,
    })

    return PartnershipScoreResponse(**response_dict)
