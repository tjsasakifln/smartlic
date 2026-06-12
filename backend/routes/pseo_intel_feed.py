"""NETINT-014 (#1519): GET /v1/pseo/intel-feed — EmbedIntelFeed widget endpoint.

Public (no auth) endpoint that returns compact market intelligence signals
for a given sector. Used by the frontend EmbedIntelFeed component on SEO
programmatic pages.

Aggregates from pncp_supplier_contracts and pncp_raw_bids:
  - New contracts this month
  - Total contract value this month
  - Active suppliers count
  - Active bids count

Cache: InMemory 1h TTL.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from schemas.pseo_intel_feed import IntelFeedResponse, IntelFeedSignal
from sectors import SECTORS

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pseo",
    tags=["pseo-intel-feed"],
)

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 3600  # 1h
_NEGATIVE_CACHE_TTL_SECONDS = 300  # 5min
_feed_cache: dict[str, tuple[dict, float]] = {}


def _cache_get(key: str) -> Optional[dict]:
    if key not in _feed_cache:
        return None
    data, ts = _feed_cache[key]
    if time.time() - ts >= _CACHE_TTL_SECONDS:
        del _feed_cache[key]
        return None
    return data


def _cache_set(key: str, data: dict, ttl: Optional[float] = None) -> None:
    _feed_cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slug_to_sector_id(slug: str) -> Optional[str]:
    """Convert URL slug to sector ID.

    'manutencao-predial' → 'manutencao_predial'
    """
    sector_id = slug.replace("-", "_")
    if sector_id in SECTORS:
        return sector_id
    return None


def _format_compact_brl(value: float) -> str:
    """Format value in compact BRL notation."""
    if value >= 1_000_000_000:
        return f"R${value / 1_000_000_000:.1f} bi"
    if value >= 1_000_000:
        return f"R${value / 1_000_000:.1f} mi"
    if value >= 1_000:
        return f"R${value / 1_000:.0f} mil"
    return f"R${value:,.0f}"


def _format_number(value: int) -> str:
    """Format integer with Brazilian locale."""
    return f"{value:,}".replace(",", ".")


# ---------------------------------------------------------------------------
# Data aggregation
# ---------------------------------------------------------------------------


def _get_sector_keywords(sector_id: str) -> set[str]:
    """Get lowercased keyword set for a sector."""
    sector = SECTORS.get(sector_id)
    if not sector:
        return set()
    return {kw.lower() for kw in sector.keywords}


def _matches_sector(objeto: str, keywords: set[str]) -> bool:
    """Check if an object/title string matches any sector keyword."""
    obj_lower = (objeto or "").lower()
    return any(kw in obj_lower for kw in keywords)


async def _aggregate_intel(sector_id: str, uf: Optional[str] = None) -> dict:
    """Query supabase and aggregate market intelligence signals.

    Returns a dict with contract_count, contract_value_total,
    active_suppliers, active_bids, generated_at.
    On failure returns an empty fallback.
    """
    from supabase_client import get_supabase, sb_execute

    keywords = _get_sector_keywords(sector_id)
    sector = SECTORS.get(sector_id)
    sector_name = sector.name if sector else sector_id

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    contract_count = 0
    contract_value_total = 0.0
    active_suppliers: set[str] = set()
    active_bids_count = 0

    try:
        # --- Query pncp_supplier_contracts ---
        sb = get_supabase()
        query = (
            sb.table("pncp_supplier_contracts")
            .select(
                "ni_fornecedor,valor_global,data_assinatura,objeto_contrato"
            )
            .eq("is_active", True)
            .gte("data_assinatura", month_start.isoformat())
        )
        if uf:
            query = query.eq("uf", uf.upper())

        builder = query.order("data_assinatura", desc=True)
        rows: list[dict] = []
        batch_size = 1000
        max_total = 5000
        offset = 0
        while len(rows) < max_total:
            end = offset + batch_size - 1
            resp = await sb_execute(builder.range(offset, end))
            batch = resp.data or []
            if not batch:
                break
            rows.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size

        # Filter by sector keywords
        for row in rows:
            obj = row.get("objeto_contrato") or ""
            if keywords and not _matches_sector(obj, keywords):
                continue
            contract_count += 1
            valor = float(row.get("valor_global") or 0)
            contract_value_total += valor
            ni = row.get("ni_fornecedor") or ""
            if ni:
                active_suppliers.add(ni)

        # --- Query pncp_raw_bids for active bids (filtered by sector keywords too) ---
        try:
            from datalake_query import query_datalake

            bids = await query_datalake(
                ufs=[uf] if uf else [],
                modo_busca="abertas",
                limit=1000,
            )
            for bid in bids:
                obj = (
                    bid.get("objeto")
                    or bid.get("titulo")
                    or bid.get("resumo")
                    or ""
                )
                if not keywords or _matches_sector(obj, keywords):
                    active_bids_count += 1
        except Exception as e:
            logger.debug("IntelFeed: datalake query failed (non-fatal): %s", e)

    except Exception as e:
        logger.warning(
            "IntelFeed: aggregation failed for sector=%s uf=%s: %s",
            sector_id, uf, e,
        )
        # Return partial data or empty fallback
        pass

    # Build signals
    signals = []

    # Signal 1: New contracts this month
    if contract_count > 0:
        signals.append(
            IntelFeedSignal(
                label=f"{_format_number(contract_count)} novos contratos este mês",
                value=_format_compact_brl(contract_value_total),
                trend="up" if contract_count > 10 else "stable",
            )
        )
    else:
        signals.append(
            IntelFeedSignal(
                label="Dados em consolidação",
                value="Contratos deste mês",
                trend=None,
            )
        )

    # Signal 2: Total value of contracts
    if contract_value_total > 0:
        signals.append(
            IntelFeedSignal(
                label="Valor total em contratos",
                value=_format_compact_brl(contract_value_total),
                trend="up" if contract_value_total > 1_000_000 else "stable",
            )
        )
    else:
        signals.append(
            IntelFeedSignal(
                label="Mercado em análise",
                value="Aguardando dados",
                trend=None,
            )
        )

    # Signal 3: Active suppliers and bids
    n_suppliers = len(active_suppliers)
    details_parts = []
    if n_suppliers > 0:
        details_parts.append(f"{_format_number(n_suppliers)} fornecedores ativos")
    if active_bids_count > 0:
        details_parts.append(f"{_format_number(active_bids_count)} licitações abertas")

    if details_parts:
        signals.append(
            IntelFeedSignal(
                label=" · ".join(details_parts),
                value=f"{sector_name}",
                trend="up" if active_bids_count > 0 else "stable",
            )
        )
    else:
        signals.append(
            IntelFeedSignal(
                label=f"Setor {sector_name}",
                value="Acompanhe as oportunidades",
                trend=None,
            )
        )

    return {
        "sector": sector_name,
        "signals": [s.model_dump() for s in signals],
        "generated_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/intel-feed",
    response_model=IntelFeedResponse,
    summary="Compact market intelligence feed for a sector (EmbedIntelFeed widget)",
)
async def get_intel_feed(
    sector: str = Query(..., description="Sector URL slug, e.g. 'engenharia'"),
    uf: Optional[str] = Query(None, description="Optional UF filter (e.g. 'SP')"),
):
    sector_id = _slug_to_sector_id(sector)
    if not sector_id:
        raise HTTPException(
            status_code=404,
            detail=f"Setor '{sector}' não encontrado",
        )

    cache_key = f"intel_feed:{sector_id}:{uf or 'BR'}"
    cached = _cache_get(cache_key)
    if cached:
        return IntelFeedResponse(**cached)

    data = await _aggregate_intel(sector_id, uf)
    _cache_set(cache_key, data)
    return IntelFeedResponse(**data)
