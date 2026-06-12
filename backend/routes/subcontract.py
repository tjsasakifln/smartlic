"""Subcontracting Intelligence routes (EPIC-SUBINTEL #1224).

All endpoints are gated by requires_subcontract_intel() (SUBINTEL-030).

Routes:
  - GET /v1/subcontract/health                       SUBINTEL-030 (#1665): Gate health
  - GET /v1/subcontract/opportunities?bid={id}&sector={id}
    SUBINTEL-022 (#1678): Subcontract pSEO block data
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from config.features import get_feature_flag
from quota.plan_auth import (
    check_subcontract_intel_access,
    get_subcontract_intel_dependency,
)
from schemas.subcontract_intel import (
    SubcontractBidOpportunityResponse,
    SubcontractReason,
    HistoricalSupplier,
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
_OPPORTUNITY_DISCLAIMER = (
    "Análise estimada com base em contratos públicos históricos. "
    "A subcontratação efetiva depende de fatores não capturados "
    "nesta análise (capacidade operacional, restrições editalícias, etc)."
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
# SUBINTEL-030 (#1665): Gate health endpoint
# ============================================================================


class _HealthResponse(BaseModel):
    """Response model for the subcontract health endpoint."""

    enabled: bool
    has_access: bool
    feature_flag: str = "SUBCONTRACT_INTEL_ENABLED"


@router.get(
    "/subcontract/health",
    summary="Subcontract Intel health/gate status (SUBINTEL-030)",
)
async def subcontract_health(
    user: dict = Depends(get_subcontract_intel_dependency()),
) -> _HealthResponse:
    """Return the gate status for the SUBINTEL vertical."""
    flag_on = get_feature_flag("SUBCONTRACT_INTEL_ENABLED")
    has_access = await check_subcontract_intel_access(user) if flag_on else False
    return _HealthResponse(
        enabled=bool(flag_on),
        has_access=has_access,
    )


# ============================================================================
# SUBINTEL-022 (#1678): Subcontract pSEO block
# ============================================================================

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

        # Supabase returns scalar JSON wrapped in a list
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
