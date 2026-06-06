"""Admin metrics routes for the founder dashboard (FOUNDER-003/005).

Provides admin-only endpoints that aggregate financial and engagement metrics
from server-side SQL functions. Includes Mixpanel tracking and audit logging
for all accesses.
"""

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from admin import require_admin
from analytics_events import track_event
from audit import audit_logger
from schemas.admin import RevenueMetricsResponse, MrrEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/metrics", tags=["admin", "metrics"])


def _parse_mrr_rows(rows: list[dict[str, Any]] | None) -> list[MrrEntry]:
    """Parse raw RPC result rows into MrrEntry models."""
    if not rows:
        return []
    entries = []
    for row in rows:
        month = str(row.get("month", ""))
        mrr_val = float(row.get("mrr", 0) or 0)
        sub_count = int(row.get("subscriber_count", 0) or 0)
        entries.append(MrrEntry(month=month, mrr=mrr_val, subscriber_count=sub_count))
    return entries


async def _call_rpc(rpc_name: str, params: dict[str, Any] | None = None) -> Any:
    """Execute a Supabase RPC and return the parsed result.

    Args:
        rpc_name: Name of the SQL function to call (e.g. 'get_mrr').
        params: Optional dict of parameters to pass to the RPC.

    Returns:
        Parsed result data from the RPC.

    Raises:
        HTTPException(502): If the Supabase call fails.
    """
    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        if params:
            result = await sb_execute(
                sb.rpc(rpc_name, params),
                category="read",
            )
        else:
            result = await sb_execute(
                sb.rpc(rpc_name),
                category="read",
            )
        return result.data
    except Exception as e:
        logger.error("FOUNDER-003: RPC %s failed: %s", rpc_name, e)
        raise HTTPException(
            status_code=502,
            detail=f"Erro ao consultar indicador: {rpc_name}",
        )


async def _get_total_subscribers() -> int:
    """Count currently active paid subscribers (non-free, non-trial plans).

    Returns:
        Number of active paid subscribers.
    """
    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("user_subscriptions")
            .select("id", count="exact")
            .eq("is_active", True)
            .in_("subscription_status", ["active", "trialing"])
            .not_.in_("plan_id", [
                "free", "free_trial", "pack_5", "pack_10", "pack_20", "master",
            ]),
            category="read",
        )
        return result.count or 0
    except Exception as e:
        logger.warning("FOUNDER-003: total_subscribers query failed: %s", e)
        return 0


@router.get("/founder", response_model=RevenueMetricsResponse)
async def get_founder_metrics(
    admin: dict = Depends(require_admin),
) -> RevenueMetricsResponse:
    """FOUNDER-003/005: Return aggregated founder dashboard metrics.

    Fetches MRR, churn rate, trial-to-paid conversion, D7 retention, ARPA,
    and total active paid subscribers. All values are non-PII aggregates.

    Fires a Mixpanel ``founder_metrics_viewed`` event with a snapshot of the
    aggregated metrics (no PII) and logs an audit event.

    Permission check is handled by ``Depends(require_admin)`` — non-admin
    users receive 403 Forbidden.
    """
    start_time = time.monotonic()

    # Fetch all metrics in parallel for performance
    import asyncio

    now = datetime.now(timezone.utc)
    mrr_start = (now - timedelta(days=365)).strftime("%Y-%m-%d")
    mrr_end = now.strftime("%Y-%m-%d")

    mrr_future = _call_rpc("get_mrr", {"start_date": mrr_start, "end_date": mrr_end})
    churn_future = _call_rpc("get_churn_rate_30d")
    trial_30d_future = _call_rpc("get_trial_to_paid_30d")
    trial_90d_future = _call_rpc("get_trial_to_paid_90d")
    retention_future = _call_rpc("get_d7_retention")
    arpa_future = _call_rpc("get_arpa")
    subscribers_future = _get_total_subscribers()

    mrr_data, churn_data, trial_30d_data, trial_90d_data, retention_data, arpa_data, total_subscribers = (
        await asyncio.gather(
            mrr_future, churn_future, trial_30d_future,
            trial_90d_future, retention_future, arpa_future,
            subscribers_future,
        )
    )

    lookup_duration_ms = round((time.monotonic() - start_time) * 1000, 1)

    # Parse MRR rows
    mrr_entries = _parse_mrr_rows(mrr_data if isinstance(mrr_data, list) else [])

    # Parse scalar metrics (RPC returns single value or [{value}])
    def _parse_scalar(raw: Any) -> float:
        if raw is None:
            return 0.0
        if isinstance(raw, list):
            if len(raw) == 0:
                return 0.0
            # Some RPCs return [{"get_churn_rate_30d": 5.0}]
            if isinstance(raw[0], dict):
                return float(list(raw[0].values())[0] if raw[0] else 0)
            return float(raw[0]) if raw[0] is not None else 0.0
        if isinstance(raw, dict):
            return float(list(raw.values())[0] if raw else 0)
        return float(raw or 0)

    churn_rate = _parse_scalar(churn_data)
    trial_to_paid_30d = _parse_scalar(trial_30d_data)
    trial_to_paid_90d = _parse_scalar(trial_90d_data)
    d7_retention = _parse_scalar(retention_data)
    arpa = _parse_scalar(arpa_data)

    response = RevenueMetricsResponse(
        mrr=mrr_entries,
        churn_rate_30d=churn_rate,
        trial_to_paid_30d=trial_to_paid_30d,
        trial_to_paid_90d=trial_to_paid_90d,
        d7_retention=d7_retention,
        arpa=arpa,
        total_subscribers=total_subscribers,
        lookup_duration_ms=lookup_duration_ms,
    )

    # --- FOUNDER-005: Mixpanel tracking (fire-and-forget, never raises) ---
    try:
        track_event("founder_metrics_viewed", {
            "user_id": admin.get("sub", admin.get("id", "unknown")),
            "mrr": response.mrr[-1].mrr if response.mrr else 0,
            "churn_rate_30d": response.churn_rate_30d,
            "trial_to_paid_30d": response.trial_to_paid_30d,
            "trial_to_paid_90d": response.trial_to_paid_90d,
            "d7_retention": response.d7_retention,
            "arpa": response.arpa,
            "total_subscribers": response.total_subscribers,
            "lookup_duration_ms": response.lookup_duration_ms,
        })
    except Exception:
        logger.warning("FOUNDER-005: track_event failed (fire-and-forget)", exc_info=True)

    # --- FOUNDER-005: Audit log (admin who accessed the dashboard) ---
    try:
        await audit_logger.log(
            event_type="admin.founder_metrics_viewed",
            actor_id=str(admin.get("sub", admin.get("id", ""))),
            details={
                "total_subscribers": response.total_subscribers,
                "churn_rate_30d": response.churn_rate_30d,
                "lookup_duration_ms": response.lookup_duration_ms,
            },
        )
    except ValueError:
        # Fallback: if event type was not registered (rare race), log via logger
        logger.info(
            "admin.founder_metrics_viewed actor=%s subscribers=%d",
            str(admin.get("sub", admin.get("id", "")))[:8],
            response.total_subscribers,
        )
    except Exception:
        logger.warning("Failed to log audit event for founder_metrics_viewed", exc_info=True)

    return response
