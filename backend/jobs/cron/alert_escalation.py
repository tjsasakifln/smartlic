"""#1865 AC4: Alert escalation loop — periodic check for unacknowledged SEV1.

Runs every 60 seconds. Checks all active SEV1 alerts and escalates
those that have not been acknowledged within:
  - 5 min  → level 1 (Slack @here, Sentry warning)
  - 15 min → level 2 (Slack @channel, Sentry fatal)

Design:
  - Lightweight: in-memory check via ``alert_manager.check_escalation()``
  - ARQ cron integration: same pattern as ``cron_monitor.py``
  - Graceful degradation: Sentry is the universal fallback
"""

from __future__ import annotations

import logging
import time

import sentry_sdk

from services.alert_manager import AlertStatus, Severity, check_escalation, cleanup_stale_alerts

logger = logging.getLogger(__name__)

# Run every 60 seconds. Override via env var.
ESCALATION_CHECK_INTERVAL_SECONDS = 60


async def run_escalation_check() -> dict:
    """Check all SEV1 alerts and escalate if unacknowledged.

    Called by ARQ cron (every 60s). Also prunes stale resolved alerts.

    Returns:
        Summary dict with keys:
            checked (int): total SEV1 alerts checked.
            escalated_level_1 (int): newly escalated to level 1.
            escalated_level_2 (int): newly escalated to level 2.
            pruned (int): stale resolved alerts removed.
    """
    now = time.time()
    escalated = check_escalation(now)
    pruned = cleanup_stale_alerts()

    level_1 = [e for e in escalated if e.status == AlertStatus.ESCALATED_1]
    level_2 = [e for e in escalated if e.status == AlertStatus.ESCALATED_2]

    # Fire Slack + Sentry for each escalation level
    for event in level_1:
        await _fire_escalation_slack(event, level=1)
        _fire_escalation_sentry(event, level=1)

    for event in level_2:
        await _fire_escalation_slack(event, level=2)
        _fire_escalation_sentry(event, level=2)

    summary = {
        "checked": len([e for e in escalated if e.severity == Severity.SEV1]),
        "escalated_level_1": len(level_1),
        "escalated_level_2": len(level_2),
        "pruned": pruned,
    }

    if escalated:
        logger.warning(
            "Escalation check complete: %s", summary
        )
    else:
        logger.debug("Escalation check complete: no escalations needed")

    return summary


async def _fire_escalation_slack(event, level: int) -> None:
    """Send escalation notification to Slack ``#alerts``."""
    import os

    import httpx

    webhook = os.getenv("SLACK_ALERTS_WEBHOOK_URL", "")
    if not webhook:
        webhook = os.getenv("SLACK_INGESTION_WEBHOOK_URL", "")
    if not webhook:
        logger.debug("No Slack webhook configured — skipping escalation Slack notification")
        return

    mention = "@here" if level == 1 else "@channel"
    color = "danger" if level == 2 else "warning"

    payload = {
        "text": (
            f":sos: *[ESCALATION LEVEL {level}] {event.title}*\n"
            f"{mention} — Alert {event.id[:8]} has been unacknowledged "
            f"for {max(5, level * 10)} minutes."
        ),
        "attachments": [
            {
                "color": color,
                "fields": [
                    {"title": "Alert ID", "value": event.id[:8], "short": True},
                    {"title": "Severity", "value": event.severity.value, "short": True},
                    {"title": "Source", "value": event.source, "short": True},
                    {
                        "title": "Description",
                        "value": event.description[:300],
                        "short": False,
                    },
                    {
                        "title": "Fired At",
                        "value": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(event.fired_at)
                        ),
                        "short": True,
                    },
                ],
                "footer": "SmartLic Alert Escalation",
                "ts": int(time.time()),
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook, json=payload)
            resp.raise_for_status()
        logger.info("Escalation level %d Slack notification sent for %s", level, event.id[:8])
    except Exception as exc:
        logger.warning("Escalation Slack notification failed: %s", exc)


def _fire_escalation_sentry(event, level: int) -> None:
    """Fire Sentry fatal for escalation level 2, error for level 1."""
    try:
        with sentry_sdk.push_scope() as scope:
            scope.set_tag("alert.escalation_level", str(level))
            scope.set_tag("alert.id", event.id)
            scope.set_tag("alert.severity", event.severity.value)
            scope.set_extra("event", {
                "title": event.title,
                "source": event.source,
                "fired_at": event.fired_at,
                "elapsed_minutes": (time.time() - event.fired_at) / 60.0,
            })
            scope.fingerprint = ["alert_escalation", event.id]
            sentry_sdk.capture_message(
                f"[ESCALATION LEVEL {level}] {event.title} — "
                f"unacknowledged for {(time.time() - event.fired_at) / 60.0:.0f} min",
                level="fatal" if level == 2 else "error",
            )
    except Exception:
        logger.debug("sentry_sdk not available — skipping escalation Sentry event")
