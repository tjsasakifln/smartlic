"""Subcontracting Intelligence routes (EPIC-SUBINTEL #1224).

All endpoints are gated by requires_subcontract_intel() (SUBINTEL-030).

Routes:
  - GET /v1/subcontract/health                       SUBINTEL-030 (#1665): Gate health
  - GET /v1/subcontract/opportunities?bid={id}&sector={id}
    SUBINTEL-022 (#1678): Subcontract pSEO block data
  - GET /v1/subcontract/regional-dependency?setor={id}
    SUBINTEL-012 (#1681): Regional Dependency heatmap data
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from auth import require_auth
from quota.plan_auth import (
    check_subcontract_intel_access,
    get_subcontract_intel_dependency,
)
from schemas.subcontract_intel import (
    HistoricalSupplier,
    RegionalDependencyItem,
    RegionalDependencyResponse,
    SubcontractBidOpportunityResponse,
    SubcontractReason,
)
from sectors import SECTORS

logger = logging.getLogger(__name__)

# Separate router for health endpoint — doesn't use requires_subcontract_intel
# dependency (which calls check_quota requiring Supabase). Instead, the health
# endpoint checks the flag + capability internally.
health_router = APIRouter(prefix="/subcontract", tags=["subcontract"])

# Main router for gated subcontract endpoints
router = APIRouter(
    tags=["subcontract"],
    dependencies=[Depends(get_subcontract_intel_dependency())],
)


class _HealthResponse(BaseModel):
    """Response model for the subcontract health endpoint."""

    enabled: bool = Field(..., description="Global feature flag state")
    has_access: bool = Field(..., description="Current user has plan capability")
    feature_flag: str = Field(
        "SUBCONTRACT_INTEL_ENABLED",
        description="Feature flag name",
    )


@health_router.get("/health")
async def subcontract_health(user: dict = Depends(require_auth)):
    """Check if the Subcontracting Intelligence vertical is accessible.

    Returns the global feature flag state and whether the authenticated user
    has the allow_subcontract_intel plan capability.
    """
    from config.features import get_feature_flag as _get_flag
    flag_enabled = _get_flag("SUBCONTRACT_INTEL_ENABLED")
    has_access = await check_subcontract_intel_access(user)
    return _HealthResponse(
        enabled=flag_enabled,
        has_access=has_access,
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_OPPORTUNITY_DISCLAIMER = (
    "Análise estimada com base em contratos públicos históricos. "
    "A subcontratação efetiva depende de fatores não capturados "
    "nesta análise (capacidade operacional, restrições editalícias, etc)."
)

_DISCLAIMER = (
    "Índice calculado com base em contratos públicos históricos "
    "disponíveis no PNCP. A distribuição real pode variar com "
    "contratos não capturados pela base."
)

_VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

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
# SUBINTEL-022 (#1678): Subcontract pSEO block
# ============================================================================


@router.get(
    "/subcontract/opportunities",
    summary="Subcontract Opportunities for Bid (SUBINTEL-022)",
    response_model=SubcontractBidOpportunityResponse,
)
async def get_subcontract_opportunities(
    request: Request,
    bid: str = Query(
        ..., description="Bid ID (pncp_id from pncp_raw_bids)."
    ),
    sector: str = Query(
        default=None,
        description="Sector ID for context (e.g., 'engenharia'). Optional.",
    ),
):
    """Return subcontract potential score and historical suppliers for a bid."""
    sector_id = sector.strip().lower() if sector else None
    if sector_id and sector_id not in SECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Setor inválido: '{sector}'. Setores válidos: {', '.join(sorted(SECTORS.keys()))}",
        )

    cache_key = f"opp:{bid}:{sector_id or 'none'}"
    cached = _get_cached(cache_key)
    if cached:
        return SubcontractBidOpportunityResponse(**cached)

    try:
        data = await _fetch_bid_opportunities(bid, sector_id)
        if data is None:
            raise HTTPException(status_code=404, detail="Edital não encontrado.")
        _set_cached(cache_key, data)
        return SubcontractBidOpportunityResponse(**data)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("subcontract opportunities failed for bid=%s: %s", bid, e)
        raise HTTPException(
            status_code=500,
            detail="Falha ao gerar oportunidades de subcontratação.",
        )


async def _fetch_bid_opportunities(
    bid_id: str,
    sector_id: Optional[str],
) -> Optional[dict]:
    """Fetch subcontract opportunities via RPC."""
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    generated_at = datetime.now(timezone.utc).isoformat()

    try:
        resp = await sb_execute(
            sb.rpc(
                "get_subcontract_opportunities_for_bid",
                {
                    "p_bid_id": bid_id,
                    "p_setor_id": sector_id,
                    "p_limit": 10,
                },
            )
        )
        raw = resp.data
        if not raw:
            return None

        if isinstance(raw, list) and len(raw) > 0:
            if isinstance(raw[0], dict) and "get_subcontract_opportunities_for_bid" in raw[0]:
                data = raw[0]["get_subcontract_opportunities_for_bid"]
            elif isinstance(raw[0], dict):
                data = raw[0]
            else:
                data = raw[0] if len(raw) == 1 else raw
        else:
            data = raw

        if isinstance(data, str):
            import json
            data = json.loads(data)

        if isinstance(data, dict) and "error" in data:
            return None

        reasons_raw = data.get("reasons") or []
        suppliers_raw = data.get("historical_suppliers") or []

        reasons = [
            SubcontractReason(
                reason=r.get("reason", ""),
                weight=float(r.get("weight", 0)),
            )
            for r in reasons_raw
        ]

        suppliers = [
            HistoricalSupplier(
                cnpj=s.get("cnpj", ""),
                razao_social=s.get("razao_social"),
                similar_contracts_count=int(s.get("similar_contracts_count", 0)),
                total_value=float(s.get("total_value", 0)),
                avg_value=float(s.get("avg_value", 0)),
                last_contract_year=int(s["last_contract_year"]) if s.get("last_contract_year") else None,
                match_reason=s.get("match_reason", ""),
            )
            for s in suppliers_raw
        ]

        return {
            "bid_id": data.get("bid_id", bid_id),
            "bid_value": float(data.get("bid_value", 0)),
            "bid_sector": data.get("bid_sector", sector_id or "geral"),
            "subcontract_potential_score": float(data.get("subcontract_potential_score", 0)),
            "reasons": [r.model_dump() for r in reasons],
            "historical_suppliers": [s.model_dump() for s in suppliers],
            "disclaimer": data.get("disclaimer", _OPPORTUNITY_DISCLAIMER),
            "generated_at": generated_at,
        }
    except Exception as e:
        logger.warning("RPC subcontract_opportunities failed: %s", e)
        raise


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
    """Return the regional dependency index for a sector."""
    sector_id = setor.strip().lower()
    if sector_id not in SECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Setor inválido: '{setor}'. Setores válidos: {', '.join(sorted(SECTORS.keys()))}",
        )

    cache_key = f"regional_dep:{sector_id}"
    cached = _get_cached(cache_key)
    if cached:
        return RegionalDependencyResponse(**cached)

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
    """Fetch and compute regional dependency index from Supabase RPC."""
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    generated_at = datetime.now(timezone.utc).isoformat()

    try:
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
        rows = await _fallback_query(sector_id, keywords, sb)

    if not rows:
        return _empty_response(sector_id, generated_at)

    uf_items: list[RegionalDependencyItem] = []
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

    uf_items.sort(key=lambda x: x.contract_count, reverse=True)

    hhi = sum((item.dependency_score / 100) ** 2 for item in uf_items)
    hhi_normalized = round(1.0 - hhi, 4)

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
        pass

    query = query.group_by("uf").order("count", desc=True)
    resp = await sb_execute(query)
    rows = resp.data or []

    if not keywords:
        return rows

    from supabase_client import sb_execute as _sb_execute

    all_query = (
        sb.table("pncp_supplier_contracts")
        .select("uf, valor_global, objeto_contrato")
        .eq("is_active", True)
        .is_("uf", "not", None)
    )
    all_resp = await _sb_execute(all_query)
    all_rows = all_resp.data or []

    filtered = []
    for row in all_rows:
        obj = (row.get("objeto_contrato") or "").lower()
        if any(kw.lower() in obj for kw in keywords):
            filtered.append(row)

    if not filtered:
        return []

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
    """Return empty response structure."""
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
