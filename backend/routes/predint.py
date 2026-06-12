"""PREDINT-021 (#1670): Predictive Intelligence API endpoints.

Exposes the Postgres RPCs from PREDINT-020 as FastAPI endpoints with:
- Feature flag gate (PREDICTIVE_INTEL_ENABLED)
- Pydantic validated schemas
- Response model on all endpoints (OpenAPI compliance)
- Redis caching via existing redis_pool

Endpoints:
    GET /v1/predint/forecast     — Demand forecast (monthly volume + UF trend)
    GET /v1/predint/seasonality   — Seasonal patterns (monthly averages)
    GET /v1/predint/renewals      — Renewal alerts (contracts expiring soon)
"""

import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from config.features import get_feature_flag
from redis_pool import get_redis_pool
from schemas.predint import (
    DemandForecastItem,
    DemandForecastResponse,
    SeasonalPatternItem,
    SeasonalPatternResponse,
    RenewalAlertItem,
    RenewalAlertResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["predint"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

# Cache TTLs (seconds)
_CACHE_FORECAST_TTL = 3600       # 1h — data changes slowly
_CACHE_SEASONALITY_TTL = 21600   # 6h — seasonal patterns are stable
_CACHE_RENEWALS_TTL = 3600       # 1h — renewals window shifts daily


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _build_cache_key(prefix: str, *parts: Optional[str]) -> str:
    """Build a Redis cache key from prefix and parts."""
    clean_parts = [str(p) if p else "all" for p in parts]
    return f"predint:{prefix}:{':'.join(clean_parts)}"


async def _get_cached_or_compute(
    cache_key: str,
    ttl: int,
    compute_fn: callable,
) -> dict:
    """Get from Redis cache or compute and store."""
    redis = await get_redis_pool()
    if redis:
        try:
            cached = await redis.get(cache_key)
            if cached:
                import json
                return json.loads(cached)
        except Exception as e:
            logger.warning("Redis cache read failed for %s: %s", cache_key, e)

    # Compute fresh data
    result = await compute_fn()

    # Store in cache if Redis available
    if redis:
        try:
            import json
            await redis.setex(cache_key, ttl, json.dumps(result))
        except Exception as e:
            logger.warning("Redis cache write failed for %s: %s", cache_key, e)

    return result


def _parse_rpc_rows(rows: list[dict]) -> list[DemandForecastItem]:
    """Parse RPC result rows into DemandForecastItem list."""
    items = []
    for row in rows:
        items.append(DemandForecastItem(
            month=str(row.get("month", "")),
            bid_count=int(row.get("bid_count", 0)),
            total_value=float(row.get("total_value", 0)),
        ))
    return items


def _calc_peak_month(items: list[SeasonalPatternItem]) -> Optional[int]:
    """Find the month with highest avg_count."""
    if not items:
        return None
    return max(items, key=lambda x: x.avg_count).month_num


# ---------------------------------------------------------------------------
# Endpoint 1: GET /v1/predint/forecast
# ---------------------------------------------------------------------------


@router.get(
    "/predint/forecast",
    summary="Demand Forecast — monthly contract volume over time",
    response_model=DemandForecastResponse,
)
async def get_demand_forecast(
    sector: Optional[str] = Query(
        default=None,
        description="Sector ID (e.g., 'alimentos'). If omitted, returns all sectors.",
    ),
    uf: Optional[str] = Query(
        default=None,
        description="UF filter (2-letter). If omitted, returns national aggregation.",
        pattern=r"^[A-Z]{2}$",
    ),
    months: int = Query(
        default=12,
        ge=1,
        le=120,
        description="Lookback period in months (1-120, default 12)",
    ),
):
    # Feature flag check
    if not get_feature_flag("PREDICTIVE_INTEL_ENABLED", True):
        return DemandForecastResponse(
            sector=sector,
            uf=uf,
            months=months,
            forecast=[],
            feature_enabled=False,
        )

    # Validate UF
    if uf:
        uf_upper = uf.strip().upper()
        if uf_upper not in _VALID_UFS:
            raise HTTPException(
                status_code=400,
                detail=f"UF invalida: '{uf}'. Use uma sigla de 2 letras valida.",
            )
    else:
        uf_upper = None

    async def _compute() -> dict:
        from supabase_client import get_supabase, sb_execute
        from resilience.budget import _run_with_budget

        sb = get_supabase()

        if uf_upper:
            # UF-specific trend — use get_uf_demand_trend RPC
            async def _query():
                resp = await sb_execute(
                    sb.rpc("get_uf_demand_trend", {
                        "uf": uf_upper,
                        "sector_id": sector,
                        "months_back": months,
                    })
                )
                return resp.data or []

            rows = await _run_with_budget(
                _query(),
                budget=5.0,
                phase="route",
                source="predint.forecast.uf_trend",
            )
        else:
            # National volume — use get_sector_monthly_volume RPC
            async def _query():
                resp = await sb_execute(
                    sb.rpc("get_sector_monthly_volume", {
                        "sector_id": sector,
                        "months_back": months,
                    })
                )
                return resp.data or []

            rows = await _run_with_budget(
                _query(),
                budget=5.0,
                phase="route",
                source="predint.forecast.national",
            )

        items = _parse_rpc_rows(rows)
        total_contracts = sum(item.bid_count for item in items)
        total_value = sum(item.total_value for item in items)

        return {
            "sector": sector,
            "uf": uf_upper,
            "months": months,
            "forecast": [item.model_dump() for item in items],
            "total_contracts": total_contracts,
            "total_value": round(total_value, 2),
            "feature_enabled": True,
        }

    cache_key = await _build_cache_key("forecast", sector, uf_upper, str(months))
    data = await _get_cached_or_compute(cache_key, _CACHE_FORECAST_TTL, _compute)

    return DemandForecastResponse(**data)


# ---------------------------------------------------------------------------
# Endpoint 2: GET /v1/predint/seasonality/{sector_id}
# ---------------------------------------------------------------------------


@router.get(
    "/predint/seasonality/{sector_id}",
    summary="Seasonal Pattern — average monthly contract distribution",
    response_model=SeasonalPatternResponse,
)
async def get_seasonal_pattern(
    sector_id: str,
):
    # Feature flag check
    if not get_feature_flag("PREDICTIVE_INTEL_ENABLED", True):
        return SeasonalPatternResponse(
            sector=sector_id,
            patterns=[],
            feature_enabled=False,
        )

    async def _compute() -> dict:
        from supabase_client import get_supabase, sb_execute
        from resilience.budget import _run_with_budget

        sb = get_supabase()

        async def _query():
            resp = await sb_execute(
                sb.rpc("get_sector_seasonal_pattern", {
                    "sector_id": sector_id,
                })
            )
            return resp.data or []

        rows = await _run_with_budget(
            _query(),
            budget=5.0,
            phase="route",
            source="predint.seasonality",
        )

        items = [
            SeasonalPatternItem(
                month_num=int(r.get("month_num", 0)),
                avg_count=float(r.get("avg_count", 0)),
                avg_value=float(r.get("avg_value", 0)),
            )
            for r in rows
        ]
        peak_month = _calc_peak_month(items)

        return {
            "sector": sector_id,
            "patterns": [item.model_dump() for item in items],
            "peak_month": peak_month,
            "feature_enabled": True,
        }

    cache_key = await _build_cache_key("seasonality", sector_id)
    data = await _get_cached_or_compute(
        cache_key, _CACHE_SEASONALITY_TTL, _compute
    )

    return SeasonalPatternResponse(**data)


# ---------------------------------------------------------------------------
# Endpoint 3: GET /v1/predint/renewals
# ---------------------------------------------------------------------------


@router.get(
    "/predint/renewals",
    summary="Renewal Alerts — contracts approaching estimated expiry",
    response_model=RenewalAlertResponse,
)
async def get_renewal_alerts(
    sector: Optional[str] = Query(
        default=None,
        description="Sector ID. If omitted, returns alerts for all sectors.",
    ),
    days: int = Query(
        default=90,
        ge=1,
        le=365,
        description="Lookahead window in days (1-365, default 90)",
    ),
):
    # Feature flag check
    if not get_feature_flag("PREDICTIVE_INTEL_ENABLED", True):
        return RenewalAlertResponse(
            sector=sector,
            days=days,
            alerts=[],
            feature_enabled=False,
        )

    async def _compute() -> dict:
        from supabase_client import get_supabase, sb_execute
        from resilience.budget import _run_with_budget

        sb = get_supabase()

        async def _query():
            resp = await sb_execute(
                sb.rpc("get_upcoming_renewals", {
                    "sector_id": sector,
                    "lookahead_days": days,
                })
            )
            return resp.data or []

        rows = await _run_with_budget(
            _query(),
            budget=5.0,
            phase="route",
            source="predint.renewals",
        )

        items = []
        for r in rows:
            expiry_str = r.get("estimated_expiry")
            if isinstance(expiry_str, str):
                try:
                    expiry_date = date.fromisoformat(expiry_str)
                except (ValueError, TypeError):
                    continue
            elif isinstance(expiry_str, date):
                expiry_date = expiry_str
            else:
                continue

            items.append(RenewalAlertItem(
                contract_id=int(r.get("contract_id", 0)),
                orgao=str(r.get("orgao", "")),
                value=float(r.get("value", 0)),
                estimated_expiry=expiry_date,
            ))

        total_value = sum(item.value for item in items)

        return {
            "sector": sector,
            "days": days,
            "alerts": [item.model_dump() for item in items],
            "total_count": len(items),
            "total_value": round(total_value, 2),
            "feature_enabled": True,
        }

    cache_key = await _build_cache_key("renewals", sector, str(days))
    data = await _get_cached_or_compute(
        cache_key, _CACHE_RENEWALS_TTL, _compute
    )

    return RenewalAlertResponse(**data)
