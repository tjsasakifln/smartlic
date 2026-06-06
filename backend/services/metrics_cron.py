"""Metrics cron wrapper — called by pg_cron daily at 02:00 BRT.

FOUNDER-002: Daily refresh of financial metrics cache.

This module provides the function that pg_cron triggers (via pg_net HTTP
request to the backend). The actual scheduling is also handled by the
lifespan background loop in ``jobs.cron.metrics_refresh``.

Usage:
    from services.metrics_cron import refresh_metrics_cache
    await refresh_metrics_cache()
"""

import logging

logger = logging.getLogger(__name__)


async def refresh_metrics_cache() -> dict:
    """Compute and cache all financial metrics.

    Called by:
    1. Pg_cron daily at 02:00 BRT (via pg_net → backend endpoint)
    2. Lifespan background loop (every 24h, see ``jobs.cron.metrics_refresh``)
    3. Admin endpoint (on-demand)

    Returns:
        Dict with computation status, e.g.:
        {"status": "ok", "metrics_count": 6}
    """
    from services.metrics_cache import compute_all_metrics, cache_metrics

    logger.info("Starting metrics cache refresh")
    metrics = await compute_all_metrics()
    await cache_metrics(metrics)
    logger.info("Metrics cache refresh complete (%d metrics)", len(metrics))
    return {"status": "ok", "metrics_count": len(metrics)}
