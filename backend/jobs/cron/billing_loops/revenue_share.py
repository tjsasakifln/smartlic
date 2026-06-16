"""RevenueShareLoop — Monthly partner revenue share report (STORY-323)."""
import asyncio
import logging
from datetime import datetime, timezone

from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)

REVENUE_SHARE_LOCK_KEY = "smartlic:revenue_share:lock"
REVENUE_SHARE_LOCK_TTL = 30 * 60


class RevenueShareLoop(BaseCronLoop):
    """Monthly revenue share report generation.

    Runs on the 1st of each month at ~12:00 UTC (09:00 BRT) and generates
    revenue share reports for all active partners.
    """

    name = "revenue_share_report"
    interval_seconds = 30 * 24 * 60 * 60  # ~monthly
    lock_key = REVENUE_SHARE_LOCK_KEY
    lock_ttl = REVENUE_SHARE_LOCK_TTL
    error_retry_seconds = 3600.0

    async def on_startup(self) -> None:
        """Schedule first run on the 1st of next month at 12:00 UTC."""
        now = datetime.now(timezone.utc)
        target_hour = 12
        if now.month == 12:
            next_run = datetime(now.year + 1, 1, 1, target_hour, 0, 0, tzinfo=timezone.utc)
        else:
            next_run = datetime(now.year, now.month + 1, 1, target_hour, 0, 0, tzinfo=timezone.utc)
        delay = max(60.0, min((next_run - now).total_seconds(), 31 * 86400.0))
        logger.info("STORY-323: first run in %.0fs (target: %s)", delay, next_run.isoformat())
        await asyncio.sleep(delay)

    async def run_once(self) -> dict:
        locked = await self._acquire_lock()
        if not locked:
            logger.info("STORY-323: Revenue share skipped — lock held")
            return {"status": "skipped", "reason": "lock_held"}
        try:
            from services.partner_service import generate_monthly_revenue_report
            now = datetime.now(timezone.utc)
            report_year = now.year - 1 if now.month == 1 else now.year
            report_month = 12 if now.month == 1 else now.month - 1
            result = await generate_monthly_revenue_report(report_year, report_month)
            logger.info(
                "STORY-323: report generated — %d/%d, %d partners, total_share=R$%.2f",
                report_month, report_year, len(result.get("partner_reports", [])),
                result.get("total_share", 0),
            )
            return result
        finally:
            await self._release_lock()
