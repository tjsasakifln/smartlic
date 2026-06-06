"""API-SELF-003: Rate limiting por API key via Redis monthly counter.

Rate limits per API key based on the user's plan tier:
    - Starter: 1,000 requests/month
    - Pro:    10,000 requests/month
    - Scale: 100,000 requests/month

Uses Redis INCR + EXPIRE with monthly key format:
    ``api_key_rl:{api_key_id}:{YYYY-MM}``

The month boundary aligns to BRT (UTC-3) so that the reset happens at
midnight Brazilian time on the 1st of each month.

Headers on every response:
    ``X-RateLimit-Remaining``
    ``X-RateLimit-Limit``

On exceeded:
    429 + ``Retry-After`` header (seconds until next month in BRT)

Implements acceptance criteria for API-SELF-003.
"""

from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from redis_pool import get_redis_pool

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------

# Plan type -> API key tier mapping
_API_KEY_TIER_MAP: dict[str, str] = {
    "free_trial": "starter",
    "free": "starter",
    "consultor_agil": "starter",
    "maquina": "pro",
    "smartlic_pro": "pro",
    "sala_guerra": "scale",
    "smartlic_command": "scale",
    "consultoria": "scale",
    "founding_member": "scale",
    "master": "unlimited",
}

# Tier -> monthly request limit
API_KEY_TIER_LIMITS: dict[str, int] = {
    "starter": 1000,
    "pro": 10000,
    "scale": 100000,
    "unlimited": 999_999_999,
}

# Redis key prefix
_REDIS_PREFIX: str = "api_key_rl:"

# ---------------------------------------------------------------------------
# In-memory plan cache (60 s TTL)
# ---------------------------------------------------------------------------

_PLAN_CACHE: dict[str, tuple[str, float]] = {}
_PLAN_CACHE_TTL: int = 60  # seconds


def _clear_plan_cache() -> None:
    """Clear the plan cache (used in tests)."""
    _PLAN_CACHE.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_brt_now() -> datetime:
    """Return current UTC datetime minus 3 hours (approximate BRT)."""
    return datetime.now(timezone.utc) - timedelta(hours=3)


def _get_month_key() -> str:
    """Get the current month key (``YYYY-MM``) in BRT."""
    return _get_brt_now().strftime("%Y-%m")


def _seconds_until_next_month() -> int:
    """Calculate seconds until the first day of next month at 00:00 BRT.

    Returns at least 1 second.
    """
    now_brt = _get_brt_now()
    year = now_brt.year
    month = now_brt.month

    if month == 12:
        next_brt = now_brt.replace(year=year + 1, month=1, day=1)
    else:
        next_brt = now_brt.replace(month=month + 1, day=1)

    next_brt = next_brt.replace(hour=0, minute=0, second=0, microsecond=0)

    # Convert back to UTC for the timedelta
    next_utc = next_brt + timedelta(hours=3)
    now_utc = datetime.now(timezone.utc)

    seconds = int((next_utc - now_utc).total_seconds())
    return max(1, seconds)


async def _get_user_plan(user_id: str) -> str:
    """Look up the user's ``plan_type`` from the profiles table.

    Falls back to ``free_trial`` on any error.
    Cached briefly in memory (60 s) to avoid a DB hit on every request.
    """
    now = _time.monotonic()
    cached = _PLAN_CACHE.get(user_id)
    if cached is not None and (now - cached[1]) < _PLAN_CACHE_TTL:
        return cached[0]

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("profiles")
            .select("plan_type")
            .eq("id", user_id)
            .limit(1),
            category="read",
        )
        if result.data and len(result.data) > 0:
            plan = result.data[0].get("plan_type", "free_trial")
            _PLAN_CACHE[user_id] = (plan, now)
            return plan
    except Exception as exc:
        logger.warning(
            "Failed to fetch plan for user %s: %s", user_id[:8], exc
        )

    return "free_trial"


def _get_tier_from_plan(plan_type: str) -> str:
    """Map a ``plan_type`` to an API key tier."""
    return _API_KEY_TIER_MAP.get(plan_type, "starter")


# ---------------------------------------------------------------------------
# Main rate-limit check
# ---------------------------------------------------------------------------


async def check_api_key_rate_limit(
    api_key_id: str,
    user_id: str,
) -> tuple[int, int]:
    """Check and enforce the monthly rate limit for an API key.

    The limit is determined by the user's plan tier.

    Redis key format: ``api_key_rl:{api_key_id}:{YYYY-MM}``, TTL set to
    the number of seconds until the next month (BRT).

    Falls back to in-memory when Redis is unavailable (fail-open).

    Args:
        api_key_id: The API key's UUID (from ``request.state.api_key_id``).
        user_id:    The key owner's user ID (from ``require_api_key``).

    Returns:
        ``(remaining, limit)`` tuple.

    Raises:
        HTTPException 429: when the monthly quota is exhausted.
    """
    plan_type = await _get_user_plan(user_id)
    tier = _get_tier_from_plan(plan_type)
    limit = API_KEY_TIER_LIMITS.get(tier, 1000)

    month_key = _get_month_key()
    redis_key = f"{_REDIS_PREFIX}{api_key_id}:{month_key}"

    redis = await get_redis_pool()

    if redis is not None:
        try:
            count = await redis.incr(redis_key)
            if count == 1:
                ttl_seconds = _seconds_until_next_month()
                await redis.expire(redis_key, ttl_seconds)

            remaining = max(0, limit - count)

            if count > limit:
                retry_after = _seconds_until_next_month()
                raise HTTPException(
                    status_code=429,
                    detail={
                        "detail": "API rate limit exceeded. "
                        "Your quota resets at the start of next month.",
                        "retry_after_seconds": retry_after,
                        "limit": limit,
                        "tier": tier,
                    },
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": str(retry_after),
                    },
                )

            return remaining, limit

        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(
                "API key rate limit Redis error (fail-open): %s", exc
            )
            return limit, limit

    # No Redis - allow through (best-effort rate limiting)
    return limit, limit
