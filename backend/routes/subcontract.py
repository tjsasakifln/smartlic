"""Subcontracting Intelligence routes (EPIC-SUBINTEL #1224).

All endpoints are gated by requires_subcontract_intel() (SUBINTEL-030).

Routes:
  - GET /v1/subcontract/regional-dependency?setor={id}
    SUBINTEL-012 (#1681): Regional Dependency heatmap data
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from quota.plan_auth import get_subcontract_intel_dependency
from schemas.subcontract_intel import (
    RegionalDependencyItem,
    RegionalDependencyResponse,
)
from sectors import SECTORS

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["subcontract"],
    dependencies=[Depends(get_subcontract_intel_dependency())],
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

_SUBCONTRACT_HIGH_RATE_SECTORS = {
    "engenharia", "informatica", "servicos_prediais",
    "vigilancia", "alimentos", "transporte_servicos",
}

_DISCLAIMER = (
    "Índice calculado com base em contratos públicos históricos "
    "disponíveis no PNCP. A distribuição real pode variar com "
    "contratos não capturados pela base."
)

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_CACHE_TTL = 4 * 60 * 60  # 4h
_cache: dict[str, tuple[dict, float]] = {}


def _get_cached(key: str) -> Optional[dict]:
    if key not in _cache:
        return None
    data, ts = _cache[key]
    if time.time() - ts >= _CACHE_TTL:
        del _cache[key]
        return None
    return data


def _set_cached(key: str, data: dict) -> None:
    _cache[key] = (data, time.time())


# ============================================================================
# SUBINTEL-012 (#1681): Regional Dependency Index
# ============================================================================


@router.get(
    "/subcontract/regional-dependency",
    summary="Regional Dependency Index (SUBINTEL-012)",
    response_model=RegionalDependencyResponse,
)
async def get_regional_dependency(
    request: Request,
    setor: str = Query(
        ..., description="Sector ID (e.g., 'engenharia'). Must exist in sectors_data.yaml."
    ),
):
    """Return the regional dependency index for a sector.

    For each UF, shows contract count, total value, and dependency percentage.
    Also computes normalized HHI and risk level.
    """
    sector_id = setor.strip().lower()
    if sector_id not in SECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Setor inválido: '{setor}'. Setores válidos: {', '.join(sorted(SECTORS.keys()))}",
        )

    # Try cache
    cache_key = f"regional_dep:{sector_id}"
    cached = _get_cached(cache_key)
    if cached:
        return RegionalDependencyResponse(**cached)

    # Get sector keywords
    sector_keywords = list(SECTORS[sector_id].keywords)

    try:
        data = await _fetch_regional_dependency(sector_id, sector_keywords)
        _set_cached(cache_key, data)
        return RegionalDependencyResponse(**data)
    except Exception as e:
        logger.error("regional_dependency failed for setor=%s: %s", sector_id, e)
        raise HTTPException(
            status_code=500,
            detail="Falha ao gerar índice de dependência regional.",
        )


async def _fetch_regional_dependency(
    sector_id: str,
    keywords: list[str],
) -> dict:
    """Fetch and compute regional dependency index from Supabase RPC.

    Falls back to direct query if RPC is unavailable.
    """
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    generated_at = datetime.now(timezone.utc).isoformat()

    try:
        # Try using the RPC first
        resp = await sb_execute(
            sb.rpc(
                "get_regional_dependency_index",
                {
                    "p_setor_id": sector_id,
                    "p_keywords": keywords if keywords else None,
                },
            )
        )
        rows = resp.data or []
    except Exception as rpc_err:
        logger.warning(
            "RPC get_regional_dependency_index failed, falling back to direct query: %s",
            rpc_err,
        )
        # Fallback: direct query with keyword matching
        rows = await _fallback_query(sector_id, keywords, sb)

    if not rows:
        return _empty_response(sector_id, generated_at)

    # Build UF distribution
    uf_items = []
    total_contracts = 0
    total_value = 0.0

    for row in rows:
        uf = (row.get("uf") or "").upper()
        if not uf or uf not in _VALID_UFS:
            continue
        count = int(row.get("contract_count") or 0)
        value = float(row.get("total_value") or 0)
        score = float(row.get("dependency_score") or 0)

        uf_items.append(
            RegionalDependencyItem(
                uf=uf,
                dependency_score=round(score, 1),
                contract_count=count,
                total_value=round(value, 2),
            )
        )
        total_contracts += count
        total_value += value

    # Sort by contract count descending
    uf_items.sort(key=lambda x: x.contract_count, reverse=True)

    # Compute normalized HHI
    hhi = sum((item.dependency_score / 100) ** 2 for item in uf_items)
    hhi_normalized = round(1.0 - hhi, 4)

    # Risk level
    if hhi_normalized >= 0.6:
        risk_level = "baixo"
    elif hhi_normalized >= 0.3:
        risk_level = "medio"
    else:
        risk_level = "alto"

    return {
        "sector_id": sector_id,
        "uf_distribution": [item.model_dump() for item in uf_items],
        "total_contracts": total_contracts,
        "total_value": round(total_value, 2),
        "coverage_ufs": len(uf_items),
        "hhi_normalized": hhi_normalized,
        "risk_level": risk_level,
        "disclaimer": _DISCLAIMER,
        "generated_at": generated_at,
    }


async def _fallback_query(
    sector_id: str,
    keywords: list[str],
    sb,
) -> list[dict]:
    """Fallback query when RPC is unavailable."""
    from supabase_client import sb_execute

    query = (
        sb.table("pncp_supplier_contracts")
        .select("uf, COUNT(*) AS contract_count, SUM(valor_global) AS total_value")
        .eq("is_active", True)
        .is_("uf", "not", None)
    )

    if keywords:
        # For fallback, we query all and filter in Python
        pass

    query = query.group_by("uf").order("count", desc=True)
    resp = await sb_execute(query)
    rows = resp.data or []

    if not keywords:
        return rows

    # Keyword filtering in Python
    from supabase_client import sb_execute as _sb_execute

    # Get all contracts for keyword matching
    all_query = (
        sb.table("pncp_supplier_contracts")
        .select("uf, valor_global, objeto_contrato")
        .eq("is_active", True)
        .is_("uf", "not", None)
    )
    all_resp = await _sb_execute(all_query)
    all_rows = all_resp.data or []

    # Filter by keywords
    filtered = []
    for row in all_rows:
        obj = (row.get("objeto_contrato") or "").lower()
        if any(kw.lower() in obj for kw in keywords):
            filtered.append(row)

    if not filtered:
        return []

    # Aggregate by UF
    from collections import defaultdict

    uf_agg: dict[str, dict] = defaultdict(lambda: {"contract_count": 0, "total_value": 0.0})
    for row in filtered:
        uf = (row.get("uf") or "").upper()
        if not uf:
            continue
        uf_agg[uf]["contract_count"] += 1
        uf_agg[uf]["total_value"] += float(row.get("valor_global") or 0)

    total = sum(v["contract_count"] for v in uf_agg.values())
    result = []
    for uf, agg in sorted(uf_agg.items(), key=lambda x: -x[1]["contract_count"]):
        result.append({
            "uf": uf,
            "contract_count": agg["contract_count"],
            "total_value": round(agg["total_value"], 2),
            "dependency_score": round(agg["contract_count"] / total * 100, 1) if total > 0 else 0,
        })

    return result


def _empty_response(sector_id: str, generated_at: str) -> dict:
    return {
        "sector_id": sector_id,
        "uf_distribution": [],
        "total_contracts": 0,
        "total_value": 0.0,
        "coverage_ufs": 0,
        "hhi_normalized": 0.0,
        "risk_level": "indisponivel",
        "disclaimer": _DISCLAIMER,
        "generated_at": generated_at,
    }


