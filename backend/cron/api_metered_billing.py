"""API-SELF-004: Metered billing cron for API usage.

Runs daily to:
    1. Count API requests per user per month from api_usage_records
    2. Check usage against tier limits and log overages
    3. Log metered billing run results for audit trail

This cron does NOT directly report to Stripe for metered billing
(Stripe metered prices require Stripe-native reporting). Instead, it
provides internal tracking that can be used for:
    - Overage alerts (when users exceed their tier limit)
    - Usage reports for admin dashboard
    - Future Stripe metered billing integration
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from cron._loop import acquire_redis_lock, release_redis_lock, daily_loop
from pipeline.budget import _run_with_budget

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_METERED_BILLING_LOCK_KEY = "smartlic:api_metered_billing:lock"
API_METERED_BILLING_LOCK_TTL = 10 * 60  # 10 minutes
API_METERED_BILLING_HOUR_UTC = 6  # 06:00 UTC = 03:00 BRT

# Per-query budget
_QUERY_BUDGET_S: float = 5.0

# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


async def run_api_metered_billing() -> dict:
    """Execute a single metered billing run with lock protection.

    Workflow:
        1. Acquire Redis distributed lock
        2. Aggregate API usage from api_usage_records by user + month
        3. Check each user's usage against their tier limit
        4. Log results to api_metered_billing_cron_log
        5. Return run summary

    Returns:
        dict with status, records_checked, records_over_limit, total_requests
    """
    lock_acquired = await acquire_redis_lock(
        API_METERED_BILLING_LOCK_KEY, API_METERED_BILLING_LOCK_TTL,
    )
    if not lock_acquired:
        logger.info("API metered billing skipped — lock already held")
        return {"status": "skipped", "reason": "lock_held"}

    try:
        return await _run_metered_billing()
    finally:
        await release_redis_lock(API_METERED_BILLING_LOCK_KEY)


async def _run_metered_billing() -> dict:
    """Core metered billing logic."""
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()

    # Determine current month
    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")
    now_iso = now.isoformat()

    # -----------------------------------------------------------------------
    # Step 1: Aggregate usage by user for current month
    # -----------------------------------------------------------------------
    try:

        async def _sync_query_usage():
            return await sb_execute(
                sb.table("api_usage_records")
                .select("user_id, month, request_count")
                .eq("month", current_month)
            )

        usage_result = await _run_with_budget(
            _sync_query_usage(),
            budget=_QUERY_BUDGET_S,
            phase="route",
            source="api_metered_billing.query_usage",
        )
    except Exception as e:
        logger.error("API metered billing: failed to query usage: %s", e)
        return {"status": "failed", "error": str(e)}

    usage_rows = usage_result.data or []
    logger.info(
        "API metered billing: %d usage records for month=%s",
        len(usage_rows),
        current_month,
    )

    if not usage_rows:
        await _log_cron_run(sb, current_month, 0, 0, None, "completed", now_iso)
        return {
            "status": "completed",
            "records_updated": 0,
            "records_over_limit": 0,
            "total_requests": 0,
        }

    # -----------------------------------------------------------------------
    # Step 2: Aggregate per user
    # -----------------------------------------------------------------------
    from stripe_api_products import get_tier_monthly_limit

    user_usage: dict[str, int] = {}
    for row in usage_rows:
        uid = row.get("user_id", "")
        count = row.get("request_count", 0) or 0
        user_usage[uid] = user_usage.get(uid, 0) + count

    # -----------------------------------------------------------------------
    # Step 3: Check each user's usage against their tier limit
    # -----------------------------------------------------------------------
    from supabase_client import get_supabase

    records_over_limit = 0
    total_requests = sum(user_usage.values())

    for uid, count in user_usage.items():
        # Fetch user's API tier
        try:
            profile_result = await _run_with_budget(
                sb_execute(
                    sb.table("profiles")
                    .select("api_tier")
                    .eq("id", uid)
                    .limit(1)
                ),
                budget=_QUERY_BUDGET_S,
                phase="route",
                source="api_metered_billing.get_profile",
            )
        except Exception:
            continue

        if not profile_result.data:
            continue

        tier = profile_result.data[0].get("api_tier")
        if not tier:
            continue

        limit = get_tier_monthly_limit(tier)
        if limit > 0 and count > limit:
            records_over_limit += 1
            logger.warning(
                "API metered billing: user=%s tier=%s usage=%d limit=%d OVERAGE",
                uid[:8],
                tier,
                count,
                limit,
            )

    # -----------------------------------------------------------------------
    # Step 4: Log results
    # -----------------------------------------------------------------------
    error_msg = None
    await _log_cron_run(
        sb, current_month, len(user_usage), total_requests, error_msg, "completed", now_iso,
    )

    logger.info(
        "API metered billing completed: %d users checked, %d over limit, %d total requests",
        len(user_usage),
        records_over_limit,
        total_requests,
    )

    return {
        "status": "completed",
        "records_checked": len(user_usage),
        "records_over_limit": records_over_limit,
        "total_requests": total_requests,
    }


async def _log_cron_run(
    sb,
    month: str,
    records_updated: int,
    total_requests: int,
    errors: str | None,
    status: str,
    run_at: str,
) -> None:
    """Log a metered billing cron run to api_metered_billing_cron_log."""
    try:

        def _sync_log():
            return sb.table("api_metered_billing_cron_log").insert({
                "run_at": run_at,
                "month": month,
                "records_updated": records_updated,
                "total_requests": total_requests,
                "errors": errors,
                "status": status,
            }).execute()

        await _run_with_budget(
            asyncio.to_thread(_sync_log),
            budget=_QUERY_BUDGET_S,
            phase="route",
            source="api_metered_billing.log_cron_run",
        )
    except Exception as e:
        logger.error("API metered billing: failed to log cron run: %s", e)


# ---------------------------------------------------------------------------
# Task registry interface
# ---------------------------------------------------------------------------


async def start_api_metered_billing_task() -> asyncio.Task:
    """Start the metered billing daily loop task.

    Uses ``daily_loop`` to run once per day at 06:00 UTC.
    Can be disabled by setting API_METERED_BILLING_ENABLED=false.
    """
    import os

    if os.getenv("API_METERED_BILLING_ENABLED", "true").lower() in ("false", "0", "no"):
        logger.info("API metered billing disabled via API_METERED_BILLING_ENABLED=false")
        return asyncio.create_task(asyncio.sleep(0), name="api_metered_billing_noop")

    task = asyncio.create_task(
        daily_loop(
            "API metered billing",
            run_api_metered_billing,
            API_METERED_BILLING_HOUR_UTC,
        ),
        name="api_metered_billing",
    )
    logger.info(
        "API-SELF-004: API metered billing task started (daily at %02d:00 UTC)",
        API_METERED_BILLING_HOUR_UTC,
    )
    return task
