"""DEGUST-001 (#1611): Intelligence Tasting route — aggregated market data for trial upsell.

GET /v1/intel/tasting — returns real supplier winning data with sector-level aggregation.
Data is REAL (from pncp_supplier_contracts), blur decision is client-side based on tier.

Feature flag: INTELLIGENCE_TASTING_ENABLED (config/features.py)
"""

import asyncio
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from config.features import get_feature_flag
from sectors import SECTORS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["intel_tasting"])

# ---------------------------------------------------------------------------
# Cache configuration
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 4 * 60 * 60  # 4h — data doesn't change in real-time
_tasting_cache: dict[str, tuple[dict, float]] = {}
_NEGATIVE_CACHE_TTL_SECONDS = 300  # 5min for errors / empty results

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}
_DEFAULT_MONTHS = 12
_MAX_MONTHS = 24

# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
from pydantic import BaseModel


class TastingWinner(BaseModel):
    """Top winner entry. cnpj/razao_social are REAL data — blur is client-side."""
    cnpj: str
    razao_social: str
    total_won: float
    contracts_count: int


class IntelTastingResponse(BaseModel):
    sector_id: str
    sector_name: str
    uf: Optional[str] = None
    period_months: int
    total_contracts_value: float
    total_winners: int
    total_contracts: int
    avg_contract_value: float
    top_winners: list[TastingWinner]
    generated_at: str
    feature_enabled: bool = True


def _get_cached(key: str) -> Optional[dict]:
    if key not in _tasting_cache:
        return None
    data, ts = _tasting_cache[key]
    if time.time() - ts >= _CACHE_TTL_SECONDS:
        del _tasting_cache[key]
        return None
    return data


def _set_cached(key: str, data: dict) -> None:
    _tasting_cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/intel/tasting",
    summary="Intelligence Tasting — aggregated supplier data for trial upsell (DEGUST-001)",
    response_model=IntelTastingResponse,
)
async def intel_tasting(
    request: Request,
    setor_id: Optional[str] = Query(
        default=None,
        description="Sector ID to filter (e.g., 'alimentos'). If omitted, returns global.",
    ),
    uf: Optional[str] = Query(
        default=None,
        description="UF filter (2-letter). If omitted, returns national aggregation.",
    ),
    meses: int = Query(
        default=_DEFAULT_MONTHS,
        ge=1,
        le=_MAX_MONTHS,
        description=f"Lookback period in months (1–{_MAX_MONTHS}, default {_DEFAULT_MONTHS})",
    ),
):
    # Feature flag check — fail-closed: if flag is off, return feature_enabled=False
    if not get_feature_flag("INTELLIGENCE_TASTING_ENABLED", True):
        return IntelTastingResponse(
            sector_id=setor_id or "global",
            sector_name="Todos os setores" if not setor_id else setor_id,
            uf=uf,
            period_months=meses,
            total_contracts_value=0,
            total_winners=0,
            total_contracts=0,
            avg_contract_value=0,
            top_winners=[],
            generated_at=datetime.now(timezone.utc).isoformat(),
            feature_enabled=False,
        )

    # Validate inputs
    uf_upper = uf.strip().upper() if uf else None
    if uf_upper and uf_upper not in _VALID_UFS:
        raise HTTPException(
            status_code=400,
            detail=f"UF inválida: '{uf}'. Use uma sigla de 2 letras válida.",
        )

    sector_id_clean = setor_id.strip().lower() if setor_id else None
    if sector_id_clean and sector_id_clean not in SECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Setor inválido: '{setor_id}'. Setores válidos: {', '.join(sorted(SECTORS.keys()))}",
        )

    # Cache key
    cache_key = f"tasting:{sector_id_clean or 'global'}:{uf_upper or 'BR'}:{meses}"
    cached = _get_cached(cache_key)
    if cached:
        return IntelTastingResponse(**cached)

    # Generate tasting data
    try:
        data = await _generate_tasting(sector_id_clean, uf_upper, meses)
        _set_cached(cache_key, data)
        return IntelTastingResponse(**data)
    except Exception as e:
        logger.error("intel_tasting generation failed for %s: %s", cache_key, e)
        raise HTTPException(status_code=500, detail="Falha ao gerar dados de inteligência.")


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------


async def _generate_tasting(
    sector_id: Optional[str],
    uf: Optional[str],
    meses: int,
) -> dict:
    """Aggregate supplier contracts from pncp_supplier_contracts.

    Returns total won value, unique winner count, top 10 winners, and average
    contract value for the given sector/UF/months combination.
    """
    from supabase_client import get_supabase, sb_execute
    from resilience.budget import _run_with_budget

    sb = get_supabase()

    now = datetime.now(timezone.utc)
    data_inicial = (now - timedelta(days=meses * 30)).strftime("%Y-%m-%d")
    generated_at = now.isoformat()
    sector_name = SECTORS[sector_id].name if sector_id else "Todos os setores"

    # Build sector keywords for object filtering
    keywords_lower: set[str] = set()
    if sector_id and sector_id in SECTORS:
        keywords_lower = {kw.lower() for kw in SECTORS[sector_id].keywords}

    async def _paginate_contracts() -> list[dict]:
        batch_size = 1000
        max_total = 10000
        all_rows: list[dict] = []
        offset = 0
        while len(all_rows) < max_total:
            end = offset + batch_size - 1
            query = (
                sb.table("pncp_supplier_contracts")
                .select(
                    "ni_fornecedor,nome_fornecedor,valor_global,data_assinatura,objeto_contrato"
                )
                .eq("is_active", True)
                .gte("data_assinatura", data_inicial)
                .order("valor_global", desc=True)
                .range(offset, end)
            )
            if uf:
                query = query.eq("uf", uf)
            resp = await sb_execute(query)
            batch = resp.data or []
            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        return all_rows

    rows = await _run_with_budget(
        _paginate_contracts(),
        budget=8.0,
        phase="route",
        source="intel_tasting._paginate_contracts",
    )

    # Filter by sector keywords if sector specified
    if keywords_lower:
        rows = [
            row for row in rows
            if any(
                kw in (row.get("objeto_contrato") or "").lower()
                for kw in keywords_lower
            )
        ]

    # Aggregate by supplier
    by_supplier: dict[str, dict] = {}
    total_value = 0.0
    for row in rows:
        cnpj = row.get("ni_fornecedor") or ""
        if not cnpj:
            continue
        nome = row.get("nome_fornecedor") or cnpj
        valor = float(row.get("valor_global") or 0)
        total_value += valor

        if cnpj not in by_supplier:
            by_supplier[cnpj] = {
                "cnpj": cnpj,
                "razao_social": nome,
                "total_won": 0.0,
                "contracts_count": 0,
            }
        by_supplier[cnpj]["total_won"] += valor
        by_supplier[cnpj]["contracts_count"] += 1

    # Sort by total won descending
    sorted_winners = sorted(
        by_supplier.values(), key=lambda x: x["total_won"], reverse=True
    )
    top_winners = sorted_winners[:10]
    total_contracts = len(rows)
    avg_value = total_value / total_contracts if total_contracts > 0 else 0.0

    return {
        "sector_id": sector_id or "global",
        "sector_name": sector_name,
        "uf": uf,
        "period_months": meses,
        "total_contracts_value": round(total_value, 2),
        "total_winners": len(by_supplier),
        "total_contracts": total_contracts,
        "avg_contract_value": round(avg_value, 2),
        "top_winners": [
            {
                "cnpj": w["cnpj"],
                "razao_social": w["razao_social"],
                "total_won": round(w["total_won"], 2),
                "contracts_count": w["contracts_count"],
            }
            for w in top_winners
        ],
        "generated_at": generated_at,
        "feature_enabled": True,
    }
