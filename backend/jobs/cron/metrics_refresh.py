"""jobs.cron.metrics_refresh — Daily financial metrics cache refresh.

FOUNDER-002: Runs once at startup, then every 24h at 02:00 BRT (05:00 UTC).
Computes all financial metrics via Supabase RPCs and caches them in Redis
with a 1-hour TTL.

Mirrors the pattern from ``auth_cleanup.py`` and sibling crons.

Schedule:
    - On startup (after app is ready)
    - Every 24h thereafter, aligned to 05:00 UTC
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

METRICS_REFRESH_INTERVAL_SECONDS = 24 * 60 * 60  # 24h
TARGET_UTC_HOUR = 5  # 05:00 UTC = 02:00 BRT


def _next_run_delay(target_hour: int = TARGET_UTC_HOUR) -> float:
    """Calculate seconds until the next target hour UTC.

    Returns a float suitable for ``asyncio.sleep()``, minimum 60s.
    """
    now = datetime.now(timezone.utc)
    next_run = now.replace(hour=target_hour, minute=0, second=0, microsecond=0)
    if now.hour >= target_hour:
        next_run += timedelta(days=1)
    delay = (next_run - now).total_seconds()
    return max(60.0, delay)


def _is_cb_or_connection_error(exc: BaseException) -> bool:
    """Best-effort detection of circuit-breaker / Supabase connection errors.

    Mirrors pattern from sibling crons to downgrade to WARNING instead of ERROR.
    """
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    return (
        "circuitbreaker" in name
        or "circuit" in msg
        or "connectionerror" in name
        or "timeout" in name
    )


async def run_metrics_refresh_once() -> dict:
    """Compute and cache all financial metrics in a single run.

    Returns:
        Dict with outcome — {"status": "ok", "metrics_count": N} on success,
        or {"status": "error", "error": "..."} on failure.
    """
    try:
        from services.metrics_cron import refresh_metrics_cache

        result = await refresh_metrics_cache()
        logger.info(
            "Metrics refresh completed: %s", result
        )
        return result
    except Exception as exc:
        if _is_cb_or_connection_error(exc):
            logger.warning("Metrics refresh skipped (Supabase/Redis unavailable): %s", exc)
            return {"status": "skipped", "error": str(exc)}
        logger.error("Metrics refresh error: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}


async def _metrics_refresh_loop() -> None:
    """Background loop — runs at startup, then every 24h at 05:00 UTC.

    Mirrors the pattern from ``auth_cleanup._auth_cleanup_loop``.
    """
    # Initial run at startup
    try:
        await run_metrics_refresh_once()
    except Exception as exc:
        if _is_cb_or_connection_error(exc):
            logger.warning("Initial metrics refresh skipped (Supabase/Redis unavailable): %s", exc)
        else:
            logger.error("Initial metrics refresh error: %s", exc, exc_info=True)

    # Schedule next run at 05:00 UTC
    delay = _next_run_delay()
    logger.info("Next metrics refresh in %.0fs (05:00 UTC)", delay)
    await asyncio.sleep(delay)

    while True:
        try:
            await run_metrics_refresh_once()
            logger.info("Next metrics refresh in 24h")
            await asyncio.sleep(METRICS_REFRESH_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            logger.info("Metrics refresh task cancelled")
            break
        except Exception as exc:
            if _is_cb_or_connection_error(exc):
                logger.warning("Metrics refresh cycle skipped: %s", exc)
            else:
                logger.error("Metrics refresh cycle error: %s", exc, exc_info=True)
            await asyncio.sleep(300)  # Retry in 5 minutes on error


async def start_metrics_refresh_task() -> asyncio.Task:
    """Lifespan hook: kick off the metrics refresh background loop.

    Call from ``register_all_cron_tasks()`` in ``scheduler.py``.
    """
    task = asyncio.create_task(
        _metrics_refresh_loop(), name="metrics_refresh"
    )
    logger.info("Metrics refresh background task started (interval: 24h, target: 05:00 UTC)")
    return task
