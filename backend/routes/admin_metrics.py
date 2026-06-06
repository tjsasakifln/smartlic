"""FOUNDER-003 (#1416): Endpoint GET /admin/metrics/revenue.

Returns JSON with MRR, churn, trial-to-paid, activation, retention, ARPA.
All rate/percentage fields are normalized to 0.0–1.0 range where applicable.

Uses the six SQL functions created by FOUNDER-001 (migration
20260606010000_add_founder_metrics_functions.sql) via Supabase RPC, plus
inline queries for activation_d7 / retention_d1 / retention_d30.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException

from admin import require_admin
from pipeline.budget import _run_with_budget
from schemas.admin import RevenueMetricsResponse
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
    """Convert a 0–100 percentage to a 0.0–1.0 rate."""
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


# ---------------------------------------------------------------------------
# Individual metric fetchers (one per SQL function / inline query)
# ---------------------------------------------------------------------------


async def _fetch_mrr(sb, period_start: str, period_end: str) -> tuple[float, int]:
    """Call get_mrr(start_date, end_date) and return (mrr, subscriber_count)
    for the most recent month in the range."""
    res = await sb_execute(
        sb.rpc("get_mrr", {"start_date": period_start, "end_date": period_end}),
        category="rpc",
    )
    rows = res.data or []
    if rows:
        latest = rows[-1]
        mrr_val = float(latest.get("mrr", 0))
        sub_count = int(latest.get("subscriber_count", 0))
        return mrr_val, sub_count
    return 0.0, 0


async def _fetch_churn(sb) -> float:
    """Call get_churn_rate_30d() and return 0–1 normalized."""
    res = await sb_execute(sb.rpc("get_churn_rate_30d"), category="rpc")
    return _pcnt_to_rate(res.data)


async def _fetch_trial_to_paid_30d(sb) -> float:
    """Call get_trial_to_paid_30d() and return 0–1 normalized."""
    res = await sb_execute(sb.rpc("get_trial_to_paid_30d"), category="rpc")
    return _pcnt_to_rate(res.data)


async def _fetch_trial_to_paid_90d(sb) -> float:
    """Call get_trial_to_paid_90d() and return 0–1 normalized."""
    res = await sb_execute(sb.rpc("get_trial_to_paid_90d"), category="rpc")
    return _pcnt_to_rate(res.data)


async def _fetch_retention_d7(sb) -> float:
    """Call get_d7_retention() and return 0–1 normalized."""
    res = await sb_execute(sb.rpc("get_d7_retention"), category="rpc")
    return _pcnt_to_rate(res.data)


async def _fetch_arpa(sb) -> float:
    """Call get_arpa() and return BRL value."""
    res = await sb_execute(sb.rpc("get_arpa"), category="rpc")
    return float(res.data or 0)


async def _fetch_activation_d7(sb) -> float:
    """Compute D7 activation: users with >=1 search session within their
    first 7 days after signup / total signups >7 days ago.

    Uses inline Supabase queries rather than a dedicated SQL function.
    Data volume is expected to be small (startup stage); the two queries
    are lightweight count operations.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=7)

    # Total signups >7 days ago
    total_res = await sb_execute(
        sb.table("profiles")
        .select("id, created_at")
        .lt("created_at", cutoff.isoformat())
        .limit(10000),
        category="read",
    )
    profiles = total_res.data or []
    total_count = len(profiles)
    if total_count == 0:
        return 0.0

    # Get all search_sessions for cohort analysis. The temporal join
    # (session within 7 days of signup) is done in Python below.
    sessions_res = await sb_execute(
        sb.table("search_sessions")
        .select("user_id, created_at")
        .limit(50000),
        category="read",
    )
    session_rows = sessions_res.data or []

    # Build a set of profile ids keyed by created_at for fast lookup
    profile_map: dict[str, datetime] = {}
    for p in profiles:
        pid = p.get("id")
        p_created = _parse_date(p.get("created_at"))
        if pid and p_created:
            profile_map[pid] = p_created

    # Count activated users (session within 7 days of signup)
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
    """Compute D1 retention: users who logged in 1–2 days after signup /
    total signups >1 day ago.

    Uses inline Supabase queries rather than a dedicated SQL function.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=1)

    # Total signups >1 day ago
    total_res = await sb_execute(
        sb.table("profiles")
        .select("id, created_at")
        .lt("created_at", cutoff.isoformat())
        .limit(10000),
        category="read",
    )
    profiles = total_res.data or []
    total_count = len(profiles)
    if total_count == 0:
        return 0.0

    # Build profile lookup
    profile_map: dict[str, datetime] = {}
    for p in profiles:
        pid = p.get("id")
        p_created = _parse_date(p.get("created_at"))
        if pid and p_created:
            profile_map[pid] = p_created

    # Get login_activity — we need logged_in_at for the temporal check
    login_res = await sb_execute(
        sb.table("login_activity")
        .select("user_id, logged_in_at")
        .limit(100000),
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
    """Compute D30 retention: users who logged in 30–31 days after signup /
    total signups >30 days ago.

    Uses inline Supabase queries rather than a dedicated SQL function.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=30)

    total_res = await sb_execute(
        sb.table("profiles")
        .select("id, created_at")
        .lt("created_at", cutoff.isoformat())
        .limit(10000),
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
        sb.table("login_activity")
        .select("user_id, logged_in_at")
        .limit(100000),
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
    activation_d7, retention_d1, retention_d30.

    All percentage fields are normalized to the 0.0–1.0 range.
    Response shape follows the FOUNDER-003 schema.

    **Requires:** admin or master role.
    **Target:** p95 <500ms (all DB calls run in parallel).
    """
    sb = get_supabase()

    # Analysis period — currently set to YTD 2026-01-01 → most recent
    # completed month. The MRR RPC uses this to compute monthly aggregates.
    now = datetime.now(timezone.utc)
    period_start = "2026-01-01"
    period_end = now.strftime("%Y-%m-%d")

    # -- Run all metrics in parallel for performance ---------------------------
    try:
        results = await asyncio.gather(
            _run_with_budget(
                _fetch_mrr(sb, period_start, period_end),
                budget=_RPC_BUDGET_S,
                phase="route",
                source="admin_metrics.mrr",
            ),
            _run_with_budget(
                _fetch_churn(sb),
                budget=_RPC_BUDGET_S,
                phase="route",
                source="admin_metrics.churn",
            ),
            _run_with_budget(
                _fetch_trial_to_paid_30d(sb),
                budget=_RPC_BUDGET_S,
                phase="route",
                source="admin_metrics.trial_to_paid_30d",
            ),
            _run_with_budget(
                _fetch_trial_to_paid_90d(sb),
                budget=_RPC_BUDGET_S,
                phase="route",
                source="admin_metrics.trial_to_paid_90d",
            ),
            _run_with_budget(
                _fetch_activation_d7(sb),
                budget=_RPC_BUDGET_S,
                phase="route",
                source="admin_metrics.activation_d7",
            ),
            _run_with_budget(
                _fetch_retention_d1(sb),
                budget=_RPC_BUDGET_S,
                phase="route",
                source="admin_metrics.retention_d1",
            ),
            _run_with_budget(
                _fetch_retention_d7(sb),
                budget=_RPC_BUDGET_S,
                phase="route",
                source="admin_metrics.retention_d7",
            ),
            _run_with_budget(
                _fetch_retention_d30(sb),
                budget=_RPC_BUDGET_S,
                phase="route",
                source="admin_metrics.retention_d30",
            ),
            _run_with_budget(
                _fetch_arpa(sb),
                budget=_RPC_BUDGET_S,
                phase="route",
                source="admin_metrics.arpa",
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
        (mrr_val, subs),
        churn,
        trial_30d,
        trial_90d,
        activation,
        ret_d1,
        ret_d7,
        ret_d30,
        arpa_val,
    ) = results

    return RevenueMetricsResponse(
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
    )
