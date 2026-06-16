"""SectorStatsLoop — Sector stats refresh (STORY-324)."""
import asyncio
import logging

from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)

SECTOR_STATS_HOUR_UTC = 6


class SectorStatsLoop(BaseCronLoop):
    """Refresh public sector statistics daily.

    Runs daily at SECTOR_STATS_HOUR_UTC and recalculates aggregate stats
    for all 15 tracked sectors.
    """

    name = "sector_stats_refresh"
    interval_seconds = 24 * 60 * 60
    error_retry_seconds = 600.0

    async def on_startup(self) -> None:
        """Schedule first run at configured hour."""
        from jobs.cron.notifications import _next_utc_hour
        delay = _next_utc_hour(SECTOR_STATS_HOUR_UTC)
        logger.info("STORY-324: first run in %.0fs (hour=%d UTC)", delay, SECTOR_STATS_HOUR_UTC)
        await asyncio.sleep(delay)

    async def run_once(self) -> dict:
        from routes.sectors_public import refresh_all_sector_stats
        refreshed = await refresh_all_sector_stats()
        logger.info("STORY-324: Sector stats refreshed: %d/15 sectors", refreshed)
        return {"refreshed": refreshed}
