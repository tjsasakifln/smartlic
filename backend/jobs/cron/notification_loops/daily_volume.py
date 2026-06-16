"""DailyVolumeLoop — Daily search volume recording (STORY-358)."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)

DAILY_VOLUME_HOUR_UTC = 7


class DailyVolumeLoop(BaseCronLoop):
    """Record number of bids processed in the last 24 hours.

    Runs daily at DAILY_VOLUME_HOUR_UTC and logs search volume metrics
    from completed search sessions.
    """

    name = "daily_volume"
    interval_seconds = 24 * 60 * 60
    error_retry_seconds = 600.0

    async def on_startup(self) -> None:
        """Schedule first run at configured hour."""
        from jobs.cron.notifications import _next_utc_hour
        delay = _next_utc_hour(DAILY_VOLUME_HOUR_UTC)
        logger.info("STORY-358: first run in %.0fs (hour=%d UTC)", delay, DAILY_VOLUME_HOUR_UTC)
        await asyncio.sleep(delay)

    async def run_once(self) -> dict:
        try:
            from supabase_client import get_supabase, sb_execute
            sb = get_supabase()
            now = datetime.now(timezone.utc)
            yesterday = (now - timedelta(hours=24)).isoformat()
            result = await sb_execute(
                sb.table("search_sessions").select("total_raw")
                .gte("created_at", yesterday).in_("status", ["completed", "completed_partial"])
            )
            sessions = result.data or []
            total_bids = sum(s.get("total_raw") or 0 for s in sessions)
            logger.info("STORY-358: %d bids across %d sessions in last 24h", total_bids, len(sessions))
            return {"total_bids_24h": total_bids, "session_count": len(sessions), "recorded_at": now.isoformat()}
        except Exception as e:
            err_name = type(e).__name__
            err_str = str(e)
            if "CircuitBreaker" in err_name or "ConnectionError" in err_name or "ConnectError" in err_str or "PGRST205" in err_str:
                logger.warning("STORY-358: Daily volume skipped (Supabase unavailable): %s", e)
            else:
                logger.error("STORY-358: Daily volume error: %s", e, exc_info=True)
            return {"total_bids_24h": 0, "session_count": 0, "error": str(e)}
