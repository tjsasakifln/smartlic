"""Issue #1916: Database connection pool monitoring for Supabase PostgreSQL.

Provides:
  1. ``get_db_pool_stats()`` — queries ``pg_stat_activity`` via RPC or falls back
     to the in-process tracked counters from ``supabase_client``.
  2. ``check_and_alert_utilization()`` — Sentry SEV3 alert when pool utilization
     >85% for more than 5 consecutive minutes (tracked via Redis).
  3. ``update_db_pool_metrics()`` — updates Prometheus gauges
     (``smartlic_db_pool_utilization``, etc.).
"""

from __future__ import annotations

import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UTILIZATION_THRESHOLD = 0.85       # 85% — triggers SEV3 gate
_SUSTAINED_WINDOW_S = 300           # 5 minutes sustained before alert
_REDIS_HIGH_KEY = "db_pool:high_utilization_since"
_REDIS_TTL = 600                    # 10 minute TTL on Redis keys

# Sentinel values returned when pool stats cannot be determined.
_MAX_CONNECTIONS_FALLBACK = 25      # default from supabase_client

# ---------------------------------------------------------------------------
# Pool stats fetcher
# ---------------------------------------------------------------------------


async def get_db_pool_stats() -> dict[str, Any]:
    """Query live connection pool statistics.

    Tries two strategies in order:
      1. Call the ``get_db_pool_stats`` Supabase RPC (queries pg_stat_activity
         directly — returns the most accurate real-time count).
      2. Fall back to the in-process tracked counters from
         ``supabase_client`` (``_pool_active_count`` / ``_POOL_MAX_CONNECTIONS``).

    Returns a dict with keys:
        ``active``, ``idle``, ``idle_in_transaction``, ``total``,
        ``max``, ``waiting``, ``utilization`` (float 0-1),
        ``source`` (``"pg_stat_activity"`` | ``"tracked"`` | ``"error"``).
    """
    # Strategy 1: Supabase RPC (pg_stat_activity)
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        resp = await sb_execute(
            sb.rpc("get_db_pool_stats"),
            category="rpc",
        )
        data = resp.data
        if data and isinstance(data, dict):
            active = int(data.get("active_connections", 0))
            idle = int(data.get("idle_connections", 0))
            idle_txn = int(data.get("idle_in_transaction", 0))
            total = int(data.get("total_connections", 0))
            max_conn = int(data.get("max_connections", _MAX_CONNECTIONS_FALLBACK))
            waiting = int(data.get("waiting_connections", 0))
            utilization = round(active / max_conn, 4) if max_conn > 0 else 0.0
            return {
                "active": active,
                "idle": idle,
                "idle_in_transaction": idle_txn,
                "total": total,
                "max": max_conn,
                "waiting": waiting,
                "utilization": utilization,
                "source": "pg_stat_activity",
            }
    except Exception as exc:
        logger.debug(
            "Issue #1916: RPC get_db_pool_stats failed, "
            "falling back to tracked counters: %s",
            exc,
        )

    # Strategy 2: In-process tracked counters
    try:
        from supabase_client import _pool_active_count, _POOL_MAX_CONNECTIONS
        active = _pool_active_count
        max_conn = _POOL_MAX_CONNECTIONS
        utilization = round(active / max_conn, 4) if max_conn > 0 else 0.0
        return {
            "active": active,
            "idle": max(0, max_conn - active),
            "idle_in_transaction": 0,
            "total": active,
            "max": max_conn,
            "waiting": 0,
            "utilization": utilization,
            "source": "tracked",
        }
    except Exception as exc:
        logger.warning("Issue #1916: Both pool stats strategies failed: %s", exc)
        return {
            "active": 0,
            "idle": 0,
            "idle_in_transaction": 0,
            "total": 0,
            "max": _MAX_CONNECTIONS_FALLBACK,
            "waiting": 0,
            "utilization": 0.0,
            "source": "error",
        }


# ---------------------------------------------------------------------------
# Utilisation check and Sentry alert
# ---------------------------------------------------------------------------


async def check_and_alert_utilization(stats: dict[str, Any] | None = None) -> None:
    """Check DB pool utilization and fire Sentry SEV3 if >85% for >5min.

    Uses a Redis key (``db_pool:high_utilization_since``) with a UTC timestamp
    as value. If utilisation stays above threshold for more than
    ``_SUSTAINED_WINDOW_S`` seconds, sends a Sentry ``capture_message`` at
    ``warning`` level.

    The Redis key is cleared when utilisation drops below threshold.
    Gracefully skips when Redis is unavailable (no alert, no error).

    Args:
        stats: Pre-fetched pool stats dict (from ``get_db_pool_stats()``).
               If ``None``, fetches fresh stats.
    """
    if stats is None:
        stats = await get_db_pool_stats()

    utilization = stats.get("utilization", 0.0)
    now = time.time()

    if utilization > _UTILIZATION_THRESHOLD:
        # Mark high-utilisation onset in Redis
        try:
            from redis_pool import get_redis_pool
            redis = await get_redis_pool()
            if redis is not None:
                # Set if absent (NX=True) — first time crossing the threshold
                was_set = await redis.set(
                    _REDIS_HIGH_KEY,
                    str(now),
                    nx=True,
                )
                if was_set:
                    logger.warning(
                        "Issue #1916: DB pool utilization > %.0f%% "
                        "(active=%d/%d, util=%.1f%%). Monitoring for sustained alert.",
                        _UTILIZATION_THRESHOLD * 100,
                        stats.get("active", 0),
                        stats.get("max", 0),
                        utilization * 100,
                    )

                # Read the onset timestamp
                onset_bytes = await redis.get(_REDIS_HIGH_KEY)
                if onset_bytes is not None:
                    onset = float(onset_bytes)
                    sustained = now - onset
                    if sustained >= _SUSTAINED_WINDOW_S:
                        _fire_sentry_alert(stats, sustained)
        except Exception as exc:
            logger.debug(
                "Issue #1916: Redis unavailable for pool alert tracking: %s",
                exc,
            )
    else:
        # Below threshold — clear the Redis key if it exists
        try:
            from redis_pool import get_redis_pool
            redis = await get_redis_pool()
            if redis is not None:
                await redis.delete(_REDIS_HIGH_KEY)
        except Exception:
            pass


def _fire_sentry_alert(stats: dict[str, Any], sustained_seconds: float) -> None:
    """Fire a Sentry SEV3 message for sustained high pool utilization.

    Dedup: uses Sentry ``fingerprint`` = ``["db_pool_high_utilization"]``
    so repeated calls within the same Sentry issue do not create separate
    issues.
    """
    active = stats.get("active", 0)
    max_conn = stats.get("max", 0)
    utilization = stats.get("utilization", 0.0)
    source = stats.get("source", "unknown")

    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("issue", "1916")
            scope.set_tag("db_pool.source", source)
            scope.set_tag("db_pool.utilization_pct", round(utilization * 100, 1))
            scope.set_tag("db_pool.sustained_seconds", int(sustained_seconds))
            scope.set_extra("db_pool_stats", stats)
            scope.fingerprint = ["db_pool_high_utilization"]
            sentry_sdk.capture_message(
                f"DB pool utilization > {_UTILIZATION_THRESHOLD * 100:.0f}% "
                f"sustained {sustained_seconds:.0f}s — "
                f"active={active}/{max_conn} ({utilization * 100:.1f}%, "
                f"source={source})",
                level="warning",
            )
    except Exception:
        logger.warning("Issue #1916: sentry_sdk not available, skipping alert")


# ---------------------------------------------------------------------------
# Prometheus metric update
# ---------------------------------------------------------------------------


async def update_db_pool_metrics() -> dict[str, Any]:
    """Fetch pool stats and update all relevant Prometheus gauges.

    Updates:
        - ``smartlic_db_pool_utilization`` (gauge, 0-1)
        - ``smartlic_supabase_pool_active_connections`` (gauge)
        - ``smartlic_supabase_pool_idle_connections`` (gauge)
        - ``smartlic_supabase_pool_max_connections`` (gauge)

    Returns the raw stats dict for callers that also need the values
    (e.g. admin endpoint aggregator).
    """
    stats = await get_db_pool_stats()

    try:
        from metrics import (
            DB_POOL_UTILIZATION,
            SUPABASE_POOL_ACTIVE,
            SUPABASE_POOL_IDLE,
            SUPABASE_POOL_MAX,
        )

        DB_POOL_UTILIZATION.set(stats.get("utilization", 0.0))
        SUPABASE_POOL_ACTIVE.set(stats.get("active", 0))
        SUPABASE_POOL_IDLE.set(stats.get("idle", 0))
        SUPABASE_POOL_MAX.set(stats.get("max", 0))
    except Exception as exc:
        logger.debug("Issue #1916: Failed to update Prometheus gauges: %s", exc)

    return stats


# ---------------------------------------------------------------------------
# Single-shot convenience: check and update in one call
# ---------------------------------------------------------------------------


async def run_db_pool_monitor() -> dict[str, Any]:
    """Convenience: fetch stats, update gauges, check threshold, fire alert.

    Designed to be called from the ARQ hourly job and from the health
    readiness check. Returns the raw stats dict.
    """
    stats = await update_db_pool_metrics()
    await check_and_alert_utilization(stats)
    logger.debug(
        "Issue #1916: Pool monitor — active=%d/%d, util=%.1f%%",
        stats.get("active", 0),
        stats.get("max", 0),
        stats.get("utilization", 0.0) * 100,
    )
    return stats
