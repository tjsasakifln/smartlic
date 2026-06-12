"""PREDINT-024 + PREDINT-021: Predictive Intelligence API endpoints.

Combines:
  - PREDINT-024: Predictive alert CRUD  (create/update/list/delete user alerts)
  - PREDINT-021: Predictive API          (forecast, seasonality, renewals)
"""

from __future__ import annotations
import logging
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_auth
from config.features import get_feature_flag
from log_sanitizer import mask_user_id
from redis_pool import get_redis_pool
from schemas.predint import (
    DemandForecastItem,
    DemandForecastResponse,
    PredictiveAlertCreate,
    PredictiveAlertUpdate,
    PredictiveAlertListResponse,
    PredictiveAlertResponse,
    RenewalAlertItem,
    RenewalAlertResponse,
    SeasonalPatternItem,
    SeasonalPatternResponse,
    row_to_alert_response,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["predint"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_MAX_ALERTS_PER_USER = 50

_VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PE", "PI", "PR",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}

# Cache TTLs (seconds)
_CACHE_FORECAST_TTL = 3600       # 1h — data changes slowly
_CACHE_SEASONALITY_TTL = 21600   # 6h — seasonal patterns are stable
_CACHE_RENEWALS_TTL = 3600       # 1h — renewals window shifts daily


# ============================================================================
# PREDINT-024: Predictive Alert CRUD helpers
# ============================================================================


async def _get_sb():
    from supabase_client import get_supabase, sb_execute
    return get_supabase(), sb_execute


async def _verify_ownership(alert_id: str, user_id: str, sb):
    from supabase_client import sb_execute
    result = await sb_execute(
        sb.table("predictive_alerts")
        .select("*")
        .eq("id", alert_id)
        .eq("user_id", user_id)
    )
    if not result.data or len(result.data) == 0:
        raise HTTPException(status_code=404, detail="Alerta preditivo nao encontrado.")
    return result.data[0]


# ============================================================================
# PREDINT-021: Predictive API helpers
# ============================================================================


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


# ============================================================================
# PREDINT-024: Predictive Alert CRUD Endpoints
# ============================================================================


@router.post("/predint/alerts", status_code=201, response_model=PredictiveAlertResponse)
async def create_predictive_alert(body: PredictiveAlertCreate, user: dict = Depends(require_auth)):
    user_id = user["id"]
    sb, sb_exec = await _get_sb()
    count_r = await sb_exec(sb.table("predictive_alerts").select("id", count="exact").eq("user_id", user_id))
    if (count_r.count or 0) >= _MAX_ALERTS_PER_USER:
        raise HTTPException(status_code=409, detail=f"Limite de {_MAX_ALERTS_PER_USER} alertas preditivos atingido.")
    now = datetime.now(timezone.utc).isoformat()
    insert_data = {
        "user_id": user_id,
        "sector_id": body.sector_id.strip(),
        "alert_type": body.alert_type,
        "threshold_value": body.threshold_value,
        "uf": body.uf.strip().upper() if body.uf else None,
        "enabled": True,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = await sb_exec(sb.table("predictive_alerts").insert(insert_data))
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=500, detail="Falha ao criar alerta preditivo.")
        logger.info(f"Predictive alert created for user {mask_user_id(user_id)}: sector={body.sector_id!r}")
        return row_to_alert_response(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating predictive alert: {e}")
        raise HTTPException(status_code=500, detail="Erro ao criar alerta preditivo.")


@router.get("/predint/alerts", response_model=PredictiveAlertListResponse)
async def list_predictive_alerts(
    enabled_only: bool = False,
    user: dict = Depends(require_auth),
):
    user_id = user["id"]
    sb, sb_exec = await _get_sb()
    try:
        query = sb.table("predictive_alerts").select("*").eq("user_id", user_id).order("created_at", desc=True)
        if enabled_only:
            query = query.eq("enabled", True)
        result = await sb_exec(query)
        alerts = [row_to_alert_response(r) for r in (result.data or [])]
        return PredictiveAlertListResponse(alerts=alerts, total=len(alerts))
    except Exception as e:
        logger.error(f"Error listing predictive alerts: {e}")
        raise HTTPException(status_code=500, detail="Erro ao listar alertas preditivos.")


@router.patch("/predint/alerts/{alert_id}", response_model=PredictiveAlertResponse)
async def update_predictive_alert(
    alert_id: str,
    body: PredictiveAlertUpdate,
    user: dict = Depends(require_auth),
):
    user_id = user["id"]
    sb, sb_exec = await _get_sb()
    await _verify_ownership(alert_id, user_id, sb)
    payload: dict = {}
    if body.sector_id is not None:
        payload["sector_id"] = body.sector_id.strip()
    if body.alert_type is not None:
        payload["alert_type"] = body.alert_type
    if body.threshold_value is not None:
        payload["threshold_value"] = body.threshold_value
    if body.uf is not None:
        payload["uf"] = body.uf.strip().upper() if body.uf else None
    if body.enabled is not None:
        payload["enabled"] = body.enabled
    if not payload:
        raise HTTPException(status_code=422, detail="Nenhum campo para atualizar.")
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    try:
        result = await sb_exec(sb.table("predictive_alerts").update(payload).eq("id", alert_id).eq("user_id", user_id))
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Alerta preditivo nao encontrado.")
        return row_to_alert_response(result.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating predictive alert: {e}")
        raise HTTPException(status_code=500, detail="Erro ao atualizar alerta preditivo.")


@router.delete("/predint/alerts/{alert_id}")
async def delete_predictive_alert(alert_id: str, user: dict = Depends(require_auth)):
    user_id = user["id"]
    sb, sb_exec = await _get_sb()
    try:
        result = await sb_exec(sb.table("predictive_alerts").delete().eq("id", alert_id).eq("user_id", user_id))
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Alerta preditivo nao encontrado.")
        logger.info(f"Predictive alert {alert_id[:8]}... deleted for user {mask_user_id(user_id)}")
        return {"success": True, "message": "Alerta preditivo removido com sucesso."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting predictive alert: {e}")
        raise HTTPException(status_code=500, detail="Erro ao remover alerta preditivo.")


# ============================================================================
# PREDINT-021: Demand Forecast
# ============================================================================


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


# ============================================================================
# PREDINT-021: Seasonal Pattern
# ============================================================================


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


# ============================================================================
# PREDINT-021: Renewal Alerts
# ============================================================================


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
