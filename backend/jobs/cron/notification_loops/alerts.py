"""AlertsLoop — Search alert email dispatch (STORY-315)."""
import asyncio
import logging
import time as _time

from config import ALERTS_ENABLED, ALERTS_HOUR_UTC
from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)

ALERTS_LOCK_KEY = "smartlic:alerts:lock"
ALERTS_LOCK_TTL = 30 * 60


class AlertsLoop(BaseCronLoop):
    """Daily search alert processing and email dispatch.

    Runs daily at ALERTS_HOUR_UTC. Matches new bids against user-defined
    alerts and sends personalised digest emails.
    """

    name = "search_alerts"
    interval_seconds = 24 * 60 * 60
    lock_key = ALERTS_LOCK_KEY
    lock_ttl = ALERTS_LOCK_TTL
    error_retry_seconds = 300.0

    async def on_startup(self) -> None:
        """Schedule first run at the configured alert hour."""
        if not ALERTS_ENABLED:
            return
        from jobs.cron.notifications import _next_utc_hour
        delay = _next_utc_hour(ALERTS_HOUR_UTC)
        logger.info("STORY-315: first run in %.0fs (hour=%d UTC)", delay, ALERTS_HOUR_UTC)
        await asyncio.sleep(delay)

    async def run_once(self) -> dict:
        """Run one alert matching + dispatch cycle."""
        if not ALERTS_ENABLED:
            return {"status": "disabled"}

        locked = await self._acquire_lock()
        if not locked:
            return {"status": "skipped", "reason": "lock_held"}

        from services.alert_matcher import match_alerts, finalize_matched_alert
        from templates.emails.alert_digest import render_alert_digest_email, get_alert_digest_subject
        from routes.alerts import get_alert_unsubscribe_url
        from email_service import send_email_async
        from metrics import ALERTS_PROCESSED, ALERTS_ITEMS_MATCHED, ALERTS_EMAILS_SENT, ALERTS_PROCESSING_DURATION

        start = _time.time()
        try:
            result = await match_alerts(max_alerts=100, batch_size=10)
            emails_sent = 0

            for payload in result.get("payloads", []):
                try:
                    items = payload.get("new_items", [])
                    if not items:
                        continue
                    alert_id = payload["alert_id"]
                    unsubscribe_url = get_alert_unsubscribe_url(alert_id)
                    alert_name = payload.get("alert_name", "suas licitacoes")
                    html = render_alert_digest_email(
                        user_name=payload["full_name"], alert_name=alert_name,
                        opportunities=items[:20], total_count=len(items),
                        unsubscribe_url=unsubscribe_url,
                    )
                    subject = get_alert_digest_subject(len(items), alert_name)
                    send_email_async(
                        to=payload["email"], subject=subject, html=html,
                        headers={"List-Unsubscribe": f"<{unsubscribe_url}>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
                        tags=[{"name": "category", "value": "alert_digest"}, {"name": "alert_id", "value": alert_id[:8]}],
                    )
                    await finalize_matched_alert(alert_id, [item["id"] for item in items if item.get("id")])
                    emails_sent += 1
                    ALERTS_EMAILS_SENT.labels(mode="individual").inc()
                    ALERTS_ITEMS_MATCHED.inc(len(items))
                except Exception as e:
                    logger.error("STORY-315: alert email failed for %s: %s", payload.get("alert_id", "?")[:8], e)

            ALERTS_PROCESSED.labels(outcome="matched").inc(result.get("matched", 0))
            ALERTS_PROCESSED.labels(outcome="skipped").inc(result.get("skipped", 0))
            ALERTS_PROCESSED.labels(outcome="error").inc(result.get("errors", 0))

            duration = _time.time() - start
            ALERTS_PROCESSING_DURATION.observe(duration)
            result["emails_sent"] = emails_sent
            result["duration_s"] = round(duration, 2)
            logger.info(
                "STORY-315: cycle complete — matched=%d, emails=%d, skipped=%d, errors=%d, duration=%.1fs",
                result.get("matched", 0), emails_sent, result.get("skipped", 0),
                result.get("errors", 0), duration,
            )
            return result
        finally:
            await self._release_lock()
