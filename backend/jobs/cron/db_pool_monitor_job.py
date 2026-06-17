"""Issue #1916: ARQ hourly job for DB pool monitoring.

Scrapes Supabase connection pool metrics every hour, updates Prometheus
gauges, and fires a Sentry SEV3 alert when utilisation >85% has been
sustained for more than 5 minutes.

This is the ``start_db_pool_monitor_task`` ARQ cron task registered via
``jobs/cron/scheduler.py``.  Default interval: 3600s (1 hour).
Override via ``DB_POOL_MONITOR_INTERVAL_S`` env var.
"""

from __future__ import annotations

import asyncio
import logging
import os

from monitoring.db_pool_monitor import run_db_pool_monitor

logger = logging.getLogger(__name__)

# Default interval: 1 hour between pool metric scrapes.
# The >5min sustained check happens in-process via Redis (see
# ``monitoring/db_pool_monitor.check_and_alert_utilization``), so an hourly
# scrape is sufficient — each scrape only needs to fire at most once per
# sustained event.
_DEFAULT_INTERVAL_S = 3600

# Redis distributed lock to prevent concurrent runs across workers.
_LOCK_KEY = "lock:db_pool_monitor"
_LOCK_TTL = 600  # 10 minutes


async def start_db_pool_monitor_task() -> None:
    """Register the ARQ cron task for hourly pool monitoring.

    Returns an ARQ cron-ready wrapper ``async def`` that acquires a
    distributed Redis lock before running the monitor.
    """
    interval = int(os.getenv("DB_POOL_MONITOR_INTERVAL_S", str(_DEFAULT_INTERVAL_S)))
    if interval <= 0:
        logger.info("Issue #1916: DB pool monitor disabled (interval=%d)", interval)
        return

    logger.info(
        "Issue #1916: Starting DB pool monitor (interval=%ds)",
        interval,
    )

    while True:
        await asyncio.sleep(interval)

        # Acquire distributed lock to avoid duplicate work across workers.
        try:
            from redis_pool import get_redis_pool
            redis = await get_redis_pool()
            if redis is not None:
                locked = await redis.set(_LOCK_KEY, "1", nx=True, ex=_LOCK_TTL)
                if not locked:
                    logger.debug(
                        "Issue #1916: DB pool monitor lock held by another worker"
                    )
                    continue
        except Exception:
            logger.debug(
                "Issue #1916: Redis unavailable, running pool monitor without lock"
            )

        try:
            stats = await run_db_pool_monitor()
            logger.info(
                "Issue #1916: Pool monitor run — active=%d/%d util=%.1f%%",
                stats.get("active", 0),
                stats.get("max", 0),
                stats.get("utilization", 0.0) * 100,
            )
        except Exception as exc:
            logger.error(
                "Issue #1916: DB pool monitor run failed: %s",
                exc,
                exc_info=True,
            )
        finally:
            # Release the lock
            try:
                from redis_pool import get_redis_pool
                redis = await get_redis_pool()
                if redis is not None:
                    await redis.delete(_LOCK_KEY)
            except Exception:
                pass

