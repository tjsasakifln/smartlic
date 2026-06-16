"""ReconciliationLoop — Stripe <-> DB subscription reconciliation (STORY-314)."""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from config import RECONCILIATION_ENABLED, RECONCILIATION_HOUR_UTC
from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)

RECONCILIATION_LOCK_KEY = "smartlic:reconciliation:lock"
RECONCILIATION_LOCK_TTL = 30 * 60


class ReconciliationLoop(BaseCronLoop):
    """Daily Stripe subscription reconciliation.

    Runs at RECONCILIATION_HOUR_UTC and compares Stripe subscriptions against
    local user_subscriptions table, reporting divergences and sending alerts.
    """

    name = "stripe_reconciliation"
    interval_seconds = 24 * 60 * 60
    lock_key = RECONCILIATION_LOCK_KEY
    lock_ttl = RECONCILIATION_LOCK_TTL
    error_retry_seconds = 300.0

    async def on_startup(self) -> None:
        """Schedule first run at the configured hour (if enabled)."""
        if not RECONCILIATION_ENABLED:
            logger.info("%s: disabled via config", self.name)
            return
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=RECONCILIATION_HOUR_UTC, minute=0, second=0, microsecond=0)
        if now.hour >= RECONCILIATION_HOUR_UTC:
            next_run += timedelta(days=1)
        delay = max(60.0, min((next_run - now).total_seconds(), 86400.0))
        logger.info("%s: first run in %.0fs (target hour=%d UTC)", self.name, delay, RECONCILIATION_HOUR_UTC)
        await asyncio.sleep(delay)

    async def run_once(self) -> dict:
        if not RECONCILIATION_ENABLED:
            return {"status": "disabled", "reason": "reconciliation_disabled"}
        locked = await self._acquire_lock()
        if not locked:
            logger.info("Reconciliation skipped — lock already held")
            return {"status": "skipped", "reason": "lock_held"}
        try:
            from services.stripe_reconciliation import reconcile_subscriptions, save_reconciliation_report, send_reconciliation_alert
            result = await reconcile_subscriptions()
            await save_reconciliation_report(result)
            await send_reconciliation_alert(result)
            logger.info("STORY-314: checked=%d, divergences=%d", result.get("total_checked", 0), result.get("divergences_found", 0))
            return result
        finally:
            await self._release_lock()
