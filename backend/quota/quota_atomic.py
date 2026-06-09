"""Atomic quota operations and organization quota helpers.

TD-007: Extracted from quota.py as part of DEBT-07 module split.
Contains all atomic DB operations for quota tracking.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from log_sanitizer import mask_user_id
from quota.quota_core import PLAN_CAPABILITIES

logger = logging.getLogger(__name__)

# MED-SEC-002: Reduced grace period (was 7, now 3) — 7 days was abusable
SUBSCRIPTION_GRACE_DAYS = 3


def get_current_month_key() -> str:
    """Get current month key (e.g., '2026-02')."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_quota_reset_date() -> datetime:
    """Get next quota reset date (1st of next month)."""
    now = datetime.now(timezone.utc)
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        return datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)


def get_monthly_quota_used(user_id: str) -> int:
    """
    Get searches used this month (lazy reset).

    If no record exists for current month, returns 0.
    Old month records are ignored (automatic reset).
    """
    from supabase_client import get_supabase
    sb = get_supabase()
    month_key = get_current_month_key()

    try:
        result = (
            sb.table("monthly_quota")
            .select("searches_count")
            .eq("user_id", user_id)
            .eq("month_year", month_key)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return result.data[0]["searches_count"]
        else:
            return 0
    except Exception as e:
        logger.error(f"Error fetching monthly quota for user {mask_user_id(user_id)}: {e}")
        return 0  # Fail open (don't block user on DB errors)


def increment_monthly_quota(user_id: str, max_quota: Optional[int] = None) -> int:
    """
    Atomically increment monthly quota by 1.

    SECURITY (Issue #189): Uses atomic database operation to prevent race conditions.
    The increment is performed using PostgreSQL's ON CONFLICT DO UPDATE with
    atomic increment expression (searches_count + 1), ensuring no lost updates
    even under concurrent requests.

    Args:
        user_id: The user's ID
        max_quota: Optional maximum quota (if provided, won't increment past this)

    Returns:
        New count after increment.
    """
    from supabase_client import get_supabase
    sb = get_supabase()
    month_key = get_current_month_key()

    try:
        try:
            result = sb.rpc(
                "increment_quota_atomic",
                {
                    "p_user_id": user_id,
                    "p_month_year": month_key,
                    "p_max_quota": max_quota,
                }
            ).execute()

            if result.data and len(result.data) > 0:
                new_count = result.data[0].get("new_count", 0)
                was_at_limit = result.data[0].get("was_at_limit", False)
                if was_at_limit:
                    logger.warning(f"User {mask_user_id(user_id)} quota increment blocked (at limit)")
                else:
                    logger.info(f"Incremented monthly quota for user {mask_user_id(user_id)}: {new_count} (atomic RPC)")
                return new_count

        except Exception as rpc_error:
            logger.debug(f"RPC increment_quota_atomic not available, using fallback: {rpc_error}")

        try:
            result = sb.rpc(
                "increment_quota_fallback_atomic",
                {"p_user_id": user_id, "p_month_year": month_key, "p_max_quota": max_quota or 999999}
            ).execute()
            if result.data is not None:
                new_count = result.data if isinstance(result.data, int) else (
                    result.data[0].get("new_count", 0) if isinstance(result.data, list) and result.data else 0
                )
                logger.info(f"Incremented monthly quota for user {mask_user_id(user_id)}: {new_count} (atomic fallback RPC)")
                return new_count
        except Exception as fallback_rpc_err:
            logger.debug(f"Atomic fallback RPC not available: {fallback_rpc_err}")

        logger.warning(
            f"All atomic quota increment methods failed for user {mask_user_id(user_id)}. "
            f"RPC increment_quota_atomic and increment_quota_fallback_atomic both unavailable. "
            f"Returning current count without increment (fail-open)."
        )
        # Lazy import via facade so test patches on quota.get_monthly_quota_used work (AC2)
        import quota as _quota
        return _quota.get_monthly_quota_used(user_id)

    except Exception as e:
        logger.error(f"Error incrementing monthly quota for user {mask_user_id(user_id)}: {e}")
        try:
            import quota as _quota
            return _quota.get_monthly_quota_used(user_id)
        except Exception:
            return 0


def check_and_increment_quota_atomic(
    user_id: str,
    max_quota: int
) -> tuple[bool, int, int]:
    """
    Atomically check quota limit and increment if allowed.

    SECURITY (Issue #189): This function eliminates the TOCTOU race condition
    by performing check and increment in a single atomic database operation.
    There is no window between check and increment where another request
    could slip through.

    STORY-291 AC4: When Supabase CB is open, allows the search (fail-open)
    and logs for reconciliation. Better to over-count than to block a user.

    Args:
        user_id: The user's ID
        max_quota: Maximum allowed quota for the user's plan

    Returns:
        tuple: (allowed: bool, new_count: int, quota_remaining: int)
            - allowed: True if increment was allowed (was under limit)
            - new_count: The new quota count after operation
            - quota_remaining: How many requests remain (0 if at/over limit)
    """
    from supabase_client import get_supabase, supabase_cb, CircuitBreakerOpenError
    sb = get_supabase()
    month_key = get_current_month_key()

    try:
        result = supabase_cb.call_sync(
            sb.rpc(
                "check_and_increment_quota",
                {
                    "p_user_id": user_id,
                    "p_month_year": month_key,
                    "p_max_quota": max_quota,
                }
            ).execute
        )

        if result.data and len(result.data) > 0:
            row = result.data[0]
            allowed = row.get("allowed", False)
            new_count = row.get("new_count", 0)
            quota_remaining = row.get("quota_remaining", 0)
            logger.info(
                f"Atomic quota check for user {mask_user_id(user_id)}: allowed={allowed}, "
                f"count={new_count}, remaining={quota_remaining}"
            )
            return (allowed, new_count, quota_remaining)

        logger.warning(f"Empty result from check_and_increment_quota for user {mask_user_id(user_id)}")
        return (True, 0, max_quota)  # Fail open

    except CircuitBreakerOpenError:
        # GAP-012 (#1590): Try Layer 2 (Redis fallback) before Layer 3 (fail-open)
        logger.warning(
            f"STORY-291 CB OPEN: Quota check Supabase offline for user "
            f"{mask_user_id(user_id)} — trying fallback layers"
        )
        from quota.quota_fallback import QUOTA_FALLBACK_MAX_DAILY, _set_quota_fallback_active, try_quota_fallback
        _set_quota_fallback_active(1)
        fallback_allowed = try_quota_fallback(user_id)
        if fallback_allowed:
            return (True, 0, max_quota)
        # Fallback limit reached — block the request
        logger.warning(
            f"Quota fallback limit reached for user {mask_user_id(user_id)} "
            f"(blocked after {QUOTA_FALLBACK_MAX_DAILY} fallback searches)"
        )
        return (False, max_quota, 0)

    except Exception as e:
        logger.error(f"Error in atomic quota check for user {mask_user_id(user_id)}: {e}")
        # GAP-012 (#1590): Try Redis fallback before falling through to lazy Supabase fallback
        from quota.quota_fallback import try_quota_fallback
        fallback_allowed = try_quota_fallback(user_id)
        if not fallback_allowed:
            return (False, max_quota, 0)
        # Lazy import via facade so test patches on quota.get_monthly_quota_used work (AC2)
        import quota as _quota
        current = _quota.get_monthly_quota_used(user_id)
        if current >= max_quota:
            return (False, current, 0)
        new_count = _quota.increment_monthly_quota(user_id, max_quota)
        return (True, new_count, max(0, max_quota - new_count))


# ============================================================================
# STORY-322 AC5/AC6: Organization-level quota helpers
# ============================================================================


def get_user_org_plan(user_id: str) -> Optional[tuple[str, str, int]]:
    """Check if user belongs to an org with consultoria plan.

    Returns (org_id, plan_type, max_requests_per_month) or None.
    Used by check_quota to switch from per-user to per-org quota pool.
    """
    try:
        from supabase_client import get_supabase
        sb = get_supabase()

        member = (
            sb.table("organization_members")
            .select("org_id, accepted_at")
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not member.data or not member.data[0].get("accepted_at"):
            return None

        org_id = member.data[0]["org_id"]
        org = (
            sb.table("organizations")
            .select("plan_type")
            .eq("id", org_id)
            .single()
            .execute()
        )
        if not org.data:
            return None

        org_plan = org.data.get("plan_type", "")
        if org_plan not in PLAN_CAPABILITIES:
            return None

        caps = PLAN_CAPABILITIES[org_plan]
        return (org_id, org_plan, caps["max_requests_per_month"])

    except Exception as e:
        logger.warning(f"Failed to check org plan for user {mask_user_id(user_id)}: {e}")
        return None


def check_and_increment_org_quota_atomic(
    org_id: str,
    user_id: str,
    max_quota: int,
) -> tuple[bool, int, int]:
    """Atomically check and increment quota at the org level.

    STORY-322 AC6: Quota is shared across all org members.
    Uses the same RPC function but with org_id as the user_id key
    (the quota table tracks by a generic subject_id).
    """
    return check_and_increment_quota_atomic(org_id, max_quota)
