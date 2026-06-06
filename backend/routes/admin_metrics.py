"""FOUNDER-003 + FOUNDER-005 (#1416, #1422): Admin revenue metrics endpoint.

Combined implementation covering both stories:
- FOUNDER-003: GET /v1/admin/metrics/revenue — MRR, churn, trial-to-paid,
  activation, retention, ARPA via FOUNDER-001 SQL functions.
- FOUNDER-005: Mixpanel ``founder_metrics_viewed`` event + audit log.

All DB calls wrapped in ``_run_with_budget()``.
Mixpanel and audit log are fire-and-forget (never break response).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from admin import require_admin
from analytics_events import track_event
from audit import audit_logger
from pipeline.budget import _run_with_budget
from schemas.admin import RevenueMetricsResponse, MrrEntry
from supabase_client import get_supabase, sb_execute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "metrics"])

# Budget for each DB call — all run in parallel so the total wall-clock time
# is bounded by the slowest single query (<200ms per the FOUNDER-001 spec).
_RPC_BUDGET_S = 5.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pcnt_to_rate(value: float | None) -> float:
    """Convert a 0-100 percentage to a 0.0-1.0 rate."""
    if value is None:
        return 0.0
    return round(float(value) / 100.0, 4)


def _parse_date(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_scalar(raw) -> float:
    """Parse a scalar RPC result."""
    if raw is None:
        return 0.0
    if isinstance(raw, list):
        if len(raw) == 0:
            return 0.0
        if isinstance(raw[0], dict):
            vals = list(raw[0].values())
            return float(vals[0]) if vals else 0.0
        return float(raw[0]) if raw[0] is not None else 0.0
    if isinstance(raw, dict):
        vals = list(raw.values())
        return float(vals[0]) if vals else 0.0
    return float(raw or 0)


# ---------------------------------------------------------------------------
# Individual metric fetchers
# ---------------------------------------------------------------------------


async def _fetch_mrr_rows(sb, period_start: str, period_end: str) -> tuple[float, int, list[MrrEntry]]:
    """Call get_mrr(start_date, end_date) and return:
    (latest_mrr, latest_subscriber_count, all_mrr_entries).
    """
    res = await sb_execute(
        sb.rpc("get_mrr", {"start_date": period_start, "end_date": period_end}),
        category="rpc",
    )
    rows = res.data or []
    entries: list[MrrEntry] = []
    latest_mrr = 0.0
    latest_subs = 0
    for row in rows:
        month = str(row.get("month", ""))
        mrr_val = float(row.get("mrr", 0))
        sub_count = int(row.get("subscriber_count", 0))
        entries.append(MrrEntry(month=month, mrr=mrr_val, subscriber_count=sub_count))
        latest_mrr = mrr_val
        latest_subs = sub_count
    return latest_mrr, latest_subs, entries


async def _fetch_churn(sb) -> float:
    """Call get_churn_rate_30d() and return 0-1 normalized."""
    res = await sb_execute(sb.rpc("get_churn_rate_30d"), category="rpc")
    return _pcnt_to_rate(_parse_scalar(res.data))


async def _fetch_trial_to_paid_30d(sb) -> float:
    """Call get_trial_to_paid_30d() and return 0-1 normalized."""
    res = await sb_execute(sb.rpc("get_trial_to_paid_30d"), category="rpc")
    return _pcnt_to_rate(_parse_scalar(res.data))


async def _fetch_trial_to_paid_90d(sb) -> float:
    """Call get_trial_to_paid_90d() and return 0-1 normalized."""
    res = await sb_execute(sb.rpc("get_trial_to_paid_90d"), category="rpc")
    return _pcnt_to_rate(_parse_scalar(res.data))


async def _fetch_retention_d7(sb) -> float:
    """Call get_d7_retention() and return 0-1 normalized."""
    res = await sb_execute(sb.rpc("get_d7_retention"), category="rpc")
    return _pcnt_to_rate(_parse_scalar(res.data))


async def _fetch_arpa(sb) -> float:
    """Call get_arpa() and return BRL value."""
    res = await sb_execute(sb.rpc("get_arpa"), category="rpc")
    return _parse_scalar(res.data)


async def _fetch_activation_d7(sb) -> float:
    """Compute D7 activation: users with >=1 search session within their
    first 7 days after signup / total signups >7 days ago.

    Uses inline Supabase queries.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    total_res = await sb_execute(
        sb.table("profiles").select("id, created_at").lt("created_at", cutoff.isoformat()).limit(10000),
        category="read",
    )
    profiles = total_res.data or []
    total_count = len(profiles)
    if total_count == 0:
        return 0.0

    sessions_res = await sb_execute(
        sb.table("search_sessions").select("user_id, created_at").limit(50000),
        category="read",
    )
    session_rows = sessions_res.data or []

    profile_map: dict[str, datetime] = {}
    for p in profiles:
        pid = p.get("id")
        p_created = _parse_date(p.get("created_at"))
        if pid and p_created:
            profile_map[pid] = p_created

    activated_ids: set[str] = set()
    for s in session_rows:
        uid = s.get("user_id")
        if uid in activated_ids:
            continue
        if uid not in profile_map:
            continue
        s_created = _parse_date(s.get("created_at"))
        if s_created is None:
            continue
        user_created = profile_map[uid]
        if timedelta(0) <= s_created - user_created <= timedelta(days=7):
            activated_ids.add(uid)

    return round(len(activated_ids) / total_count, 4)


async def _fetch_retention_d1(sb) -> float:
    """Compute D1 retention: users who logged in 1-2 days after signup /
    total signups >1 day ago.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)

    total_res = await sb_execute(
        sb.table("profiles").select("id, created_at").lt("created_at", cutoff.isoformat()).limit(10000),
        category="read",
    )
    profiles = total_res.data or []
    total_count = len(profiles)
    if total_count == 0:
        return 0.0

    profile_map: dict[str, datetime] = {}
    for p in profiles:
        pid = p.get("id")
        p_created = _parse_date(p.get("created_at"))
        if pid and p_created:
            profile_map[pid] = p_created

    login_res = await sb_execute(
        sb.table("login_activity").select("user_id, logged_in_at").limit(100000),
        category="read",
    )
    login_rows = login_res.data or []

    retained_ids: set[str] = set()
    for la in login_rows:
        uid = la.get("user_id")
        if uid in retained_ids:
            continue
        if uid not in profile_map:
            continue
        login_time = _parse_date(la.get("logged_in_at"))
        if login_time is None:
            continue
        user_created = profile_map[uid]
        delta = login_time - user_created
        if timedelta(days=1) <= delta < timedelta(days=2):
            retained_ids.add(uid)

    return round(len(retained_ids) / total_count, 4)


async def _fetch_retention_d30(sb) -> float:
    """Compute D30 retention: users who logged in 30-31 days after signup /
    total signups >30 days ago.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)

    total_res = await sb_execute(
        sb.table("profiles").select("id, created_at").lt("created_at", cutoff.isoformat()).limit(10000),
        category="read",
    )
    profiles = total_res.data or []
    total_count = len(profiles)
    if total_count == 0:
        return 0.0

    profile_map: dict[str, datetime] = {}
    for p in profiles:
        pid = p.get("id")
        p_created = _parse_date(p.get("created_at"))
        if pid and p_created:
            profile_map[pid] = p_created

    login_res = await sb_execute(
        sb.table("login_activity").select("user_id, logged_in_at").limit(100000),
        category="read",
    )
    login_rows = login_res.data or []

    retained_ids: set[str] = set()
    for la in login_rows:
        uid = la.get("user_id")
        if uid in retained_ids:
            continue
        if uid not in profile_map:
            continue
        login_time = _parse_date(la.get("logged_in_at"))
        if login_time is None:
            continue
        user_created = profile_map[uid]
        delta = login_time - user_created
        if timedelta(days=30) <= delta < timedelta(days=31):
            retained_ids.add(uid)

    return round(len(retained_ids) / total_count, 4)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/metrics/revenue", response_model=RevenueMetricsResponse)
async def get_revenue_metrics(
    admin: dict = Depends(require_admin),
) -> RevenueMetricsResponse:
    """Return financial and engagement metrics for the founder dashboard.

    Calls six PostgreSQL functions (FOUNDER-001) + inline queries for
    activation_d7, retention_d1, retention_d30. All DB calls run in
    parallel via ``asyncio.gather``.

    Fires a Mixpanel ``founder_metrics_viewed`` event and logs an audit
    event. Both are fire-and-forget — they never block the response.

    **Requires:** admin or master role.
    """
    sb = get_supabase()

    now = datetime.now(timezone.utc)
    period_start = "2026-01-01"
    period_end = now.strftime("%Y-%m-%d")

    # -- Run all metrics in parallel -----------------------------------------
    try:
        results = await asyncio.gather(
            _run_with_budget(
                _fetch_mrr_rows(sb, period_start, period_end),
                budget=_RPC_BUDGET_S, phase="route", source="admin_metrics.mrr",
            ),
            _run_with_budget(
                _fetch_churn(sb),
                budget=_RPC_BUDGET_S, phase="route", source="admin_metrics.churn",
            ),
            _run_with_budget(
                _fetch_trial_to_paid_30d(sb),
                budget=_RPC_BUDGET_S, phase="route", source="admin_metrics.trial_30d",
            ),
            _run_with_budget(
                _fetch_trial_to_paid_90d(sb),
                budget=_RPC_BUDGET_S, phase="route", source="admin_metrics.trial_90d",
            ),
            _run_with_budget(
                _fetch_activation_d7(sb),
                budget=_RPC_BUDGET_S, phase="route", source="admin_metrics.activation_d7",
            ),
            _run_with_budget(
                _fetch_retention_d1(sb),
                budget=_RPC_BUDGET_S, phase="route", source="admin_metrics.retention_d1",
            ),
            _run_with_budget(
                _fetch_retention_d7(sb),
                budget=_RPC_BUDGET_S, phase="route", source="admin_metrics.retention_d7",
            ),
            _run_with_budget(
                _fetch_retention_d30(sb),
                budget=_RPC_BUDGET_S, phase="route", source="admin_metrics.retention_d30",
            ),
            _run_with_budget(
                _fetch_arpa(sb),
                budget=_RPC_BUDGET_S, phase="route", source="admin_metrics.arpa",
            ),
        )
    except asyncio.TimeoutError:
        logger.warning("admin_metrics get_revenue_metrics exceeded aggregate budget")
        raise HTTPException(
            status_code=503,
            detail="Metricas financeiras temporariamente indisponiveis (timeout)",
        )
    except Exception as e:
        logger.error("admin_metrics get_revenue_metrics failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Erro ao calcular metricas financeiras",
        )

    (
        (mrr_val, subs, mrr_history),
        churn,
        trial_30d,
        trial_90d,
        activation,
        ret_d1,
        ret_d7,
        ret_d30,
        arpa_val,
    ) = results

    response = RevenueMetricsResponse(
        mrr=mrr_val,
        churn_rate_30d=churn,
        trial_to_paid_30d=trial_30d,
        trial_to_paid_90d=trial_90d,
        activation_d7=activation,
        retention_d1=ret_d1,
        retention_d7=ret_d7,
        retention_d30=ret_d30,
        arpa=arpa_val,
        total_subscribers=subs,
        period_start=period_start,
        period_end=period_end,
        mrr_history=mrr_history,
    )

    # -- FOUNDER-005: Mixpanel tracking (fire-and-forget, never raises) ------
    try:
        track_event("founder_metrics_viewed", {
            "user_id": admin.get("sub", admin.get("id", "unknown")),
            "mrr": response.mrr,
            "churn_rate_30d": response.churn_rate_30d,
            "trial_to_paid_30d": response.trial_to_paid_30d,
            "trial_to_paid_90d": response.trial_to_paid_90d,
            "activation_d7": response.activation_d7,
            "arpa": response.arpa,
            "total_subscribers": response.total_subscribers,
        })
    except Exception:
        logger.warning("FOUNDER-005: track_event failed (fire-and-forget)", exc_info=True)

    # -- FOUNDER-005: Audit log (fire-and-forget, never raises) --------------
    try:
        await audit_logger.log(
            event_type="admin.founder_metrics_viewed",
            actor_id=str(admin.get("sub", admin.get("id", ""))),
            details={
                "total_subscribers": response.total_subscribers,
                "mrr": response.mrr,
                "churn_rate_30d": response.churn_rate_30d,
            },
        )
    except ValueError:
        logger.info(
            "admin.founder_metrics_viewed actor=%s subscribers=%d",
            str(admin.get("sub", admin.get("id", "")))[:8],
            response.total_subscribers,
        )
    except Exception:
        logger.warning("Failed to log audit event for founder_metrics_viewed", exc_info=True)

    return response
