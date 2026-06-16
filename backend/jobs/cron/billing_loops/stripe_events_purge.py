"""StripeEventsPurgeLoop — Old Stripe webhook event cleanup (HARDEN-028)."""
import logging
from datetime import datetime, timezone, timedelta

from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)

STRIPE_EVENTS_RETENTION_DAYS = 90
STRIPE_PURGE_INTERVAL_SECONDS = 24 * 60 * 60


class StripeEventsPurgeLoop(BaseCronLoop):
    """Purge old Stripe webhook events from the database.

    Runs daily and deletes ``stripe_webhook_events`` rows older than
    ``STRIPE_EVENTS_RETENTION_DAYS`` (default 90 days).
    """

    name = "stripe_events_purge"
    interval_seconds = STRIPE_PURGE_INTERVAL_SECONDS
    error_retry_seconds = 300.0

    async def run_once(self) -> dict:
        try:
            from supabase_client import get_supabase, sb_execute
            sb = get_supabase()
            cutoff = (datetime.now(timezone.utc) - timedelta(days=STRIPE_EVENTS_RETENTION_DAYS)).isoformat()
            result = await sb_execute(sb.table("stripe_webhook_events").delete().lt("processed_at", cutoff))
            deleted = len(result.data) if result and result.data else 0
            logger.info("HARDEN-028: Purged %d events older than %d days", deleted, STRIPE_EVENTS_RETENTION_DAYS)
            return {"deleted": deleted, "cutoff": cutoff}
        except Exception as e:
            err_name = type(e).__name__
            err_str = str(e)
            if "CircuitBreaker" in err_name or "ConnectionError" in err_name or "ConnectError" in err_str or "PGRST205" in err_str:
                logger.warning("HARDEN-028: Purge skipped (Supabase unavailable): %s", e)
            else:
                logger.error("HARDEN-028: Purge error: %s", e, exc_info=True)
            return {"deleted": 0, "error": str(e)}
