"""3-layer quota fallback for Supabase offline scenarios.

GAP-012 (#1590): When Supabase is unreachable, the quota system falls through
three layers of increasing degrade:

  Layer 1 — Supabase normal: quota via RPC check_and_increment_quota.
  Layer 2 — Supabase offline: Redis counter ``quota:fallback:{user_id}``
            with conservative limit (default 10/day) + 86400s TTL.
  Layer 3 — Redis also offline: fail open (allows the request) +
            Sentry ``capture_message(level="critical")``.

Configurable via env:
  QUOTA_FALLBACK_MAX_DAILY  — max fallback requests per user per day (default: 10)
  QUOTA_FALLBACK_TTL        — Redis key TTL in seconds (default: 86400 = 24h)

This module exposes a **sync** interface because it is called from
``check_and_increment_quota_atomic`` which runs inside ``asyncio.to_thread()``
(no event loop available).  Sync Redis access is provided by
``redis_pool.get_sync_redis()``.
"""

import logging
import os
from typing import Optional

from log_sanitizer import mask_user_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

QUOTA_FALLBACK_MAX_DAILY = int(os.getenv("QUOTA_FALLBACK_MAX_DAILY", "10"))
QUOTA_FALLBACK_TTL = int(os.getenv("QUOTA_FALLBACK_TTL", "86400"))

# Redis key namespace
_FALLBACK_KEY_TEMPLATE = "quota:fallback:{user_id}"


# ---------------------------------------------------------------------------
# Public API (sync — safe for asyncio.to_thread context)
# ---------------------------------------------------------------------------


def try_quota_fallback(user_id: str) -> bool:
    """Attempt to grant quota allowance through the fallback chain.

    This is the **sync** entry-point designed to be called from
    ``check_and_increment_quota_atomic`` (which runs in a thread pool).

    Layer 2 (Redis) — atomic INCR via sync Redis client.
    Layer 3 (fail open) — Sentry critical alert, returns True.

    Args:
        user_id: The user's ID string.

    Returns:
        True if the request is allowed through fallback,
        False if the daily fallback limit has been reached.
    """
    # ---- Layer 2: Redis (sync) ----
    count = _try_redis_fallback_sync(user_id)
    if count is not None:
        allowed = count <= QUOTA_FALLBACK_MAX_DAILY
        level = "info" if allowed else "warning"
        logger.log(
            getattr(logging, level.upper()),
            "Quota fallback [Layer 2 / Redis] user=%s count=%d/%d allowed=%s",
            mask_user_id(user_id),
            count,
            QUOTA_FALLBACK_MAX_DAILY,
            allowed,
        )
        return allowed

    # ---- Layer 3: Fail open (Redis also offline) ----
    _sentry_critical(
        "Layer 3 fail-open: Supabase AND Redis both offline for quota check "
        "— allowing request without counting. user=%s",
        mask_user_id(user_id),
    )
    logger.critical(
        "Quota fallback [Layer 3 / fail-open] user=%s — Supabase and Redis "
        "both offline, allowing request uncounted",
        mask_user_id(user_id),
    )
    return True


# ---------------------------------------------------------------------------
# Layer-2 helper (sync Redis)
# ---------------------------------------------------------------------------


def _try_redis_fallback_sync(user_id: str) -> Optional[int]:
    """Try Layer-2 Redis fallback counter using the sync Redis client.

    Atomically INCR the key and set TTL on first creation (via Lua script).
    Returns the new counter value on success, or None if Redis is unavailable.

    Uses ``redis_pool.get_sync_redis()`` — safe for thread-pool context.
    """
    try:
        from redis_pool import get_sync_redis

        redis = get_sync_redis()
        if redis is None:
            return None  # Redis unavailable — escalate to Layer 3

        key = _FALLBACK_KEY_TEMPLATE.format(user_id=user_id)

        # Lua script: INCR atomically + set EXPIRE only if not already set.
        script = """
            local count = redis.call("INCR", KEYS[1])
            local ttl = redis.call("TTL", KEYS[1])
            if ttl == -1 then
                redis.call("EXPIRE", KEYS[1], ARGV[1])
            end
            return count
        """
        count = redis.eval(script, 1, key, QUOTA_FALLBACK_TTL)
        return int(count)

    except Exception as exc:
        logger.warning(
            "Redis fallback counter failed for user %s: %s",
            mask_user_id(user_id),
            exc,
        )
        return None  # Escalate to Layer 3


# ---------------------------------------------------------------------------
# Layer-3 helper
# ---------------------------------------------------------------------------


def _sentry_critical(message: str, *args) -> None:
    """Send a CRITICAL-level message to Sentry (fail-safe)."""
    try:
        import sentry_sdk

        sentry_sdk.capture_message(message % args if args else message, level="critical")
    except Exception:
        pass  # Sentry itself may not be configured — never throw here


# ---------------------------------------------------------------------------
# Metric helper (shared with quota_atomic)
# ---------------------------------------------------------------------------


def _set_quota_fallback_active(value: int) -> None:
    """Update the QUOTA_FALLBACK_ACTIVE Prometheus gauge (no-op if unavailable)."""
    try:
        from metrics import QUOTA_FALLBACK_ACTIVE

        QUOTA_FALLBACK_ACTIVE.set(value)
    except Exception:
        pass  # Graceful degradation when metrics are not configured


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "QUOTA_FALLBACK_MAX_DAILY",
    "QUOTA_FALLBACK_TTL",
    "_set_quota_fallback_active",
    "try_quota_fallback",
]
