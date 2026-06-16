"""#1865 — Alert Manager: SEV classification, dispatch, and escalation.

Defines three severity tiers (SEV1/SEV2/SEV3) with objective thresholds,
routes alerts to the appropriate channel (PagerDuty/Opsgenie → Slack →
daily digest), and tracks acknowledgment state for escalation.

Architecture:
  alert_manager.py (classification + dispatch)
      ├── services/slack_notifier.py  (SEV2 Slack dispatch)
      ├── sentry_sdk                  (fallback for all tiers)
      └── supabase_client             (alert_acknowledgments table)
"""

from __future__ import annotations

import enum
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants — severity thresholds
# ---------------------------------------------------------------------------

# SEV1: backend DOWN >60s, 5xx >5% of requests, Stripe webhook failure
SEV1_HEALTH_READY_FAIL_SECONDS = 60
SEV1_5XX_RATIO = 0.05
SEV1_STRIPE_WEBHOOK_FAILURE = True

# SEV2: latency p95 > 2s, Redis DOWN > 5min, API quota exhaustion
SEV2_LATENCY_P95_SECONDS = 2.0
SEV2_REDIS_DOWN_SECONDS = 300
SEV2_API_QUOTA_EXHAUSTION = True

# SEV3: cache hit rate < 50%, DB pool > 85%, cron job delayed > 1h
SEV3_CACHE_HIT_RATIO = 0.50
SEV3_DB_POOL_RATIO = 0.85
SEV3_CRON_DELAY_SECONDS = 3600

# ---------------------------------------------------------------------------
# Environment — channel configuration
# ---------------------------------------------------------------------------

_PAGERDUTY_ROUTING_KEY: str = os.getenv("PAGERDUTY_ROUTING_KEY", "")
_OPSGENIE_API_KEY: str = os.getenv("OPSGENIE_API_KEY", "")
_OPSGENIE_EU_ENDPOINT = "https://api.eu.opsgenie.com/v2/alerts"
_OPSGENIE_US_ENDPOINT = "https://api.opsgenie.com/v2/alerts"
_OPSGENIE_REGION: str = os.getenv("OPSGENIE_REGION", "us")
_SLACK_ALERTS_WEBHOOK_URL: str = os.getenv("SLACK_ALERTS_WEBHOOK_URL", "")
_SEV1_ESCALATION_MINUTES: tuple[int, int] = (5, 15)

_TIMEOUT_S = 10.0
_ALERT_TTL_HOURS = 48


# ---------------------------------------------------------------------------
# Enums & data classes
# ---------------------------------------------------------------------------


class Severity(str, enum.Enum):
    """Three-tier severity classification matching AC1 thresholds."""

    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"


class AlertStatus(str, enum.Enum):
    """Lifecycle states for an active alert."""

    FIRED = "fired"
    ACKNOWLEDGED = "acknowledged"
    ESCALATED_1 = "escalated_1"  # first escalation level
    ESCALATED_2 = "escalated_2"  # second escalation level
    RESOLVED = "resolved"


@dataclass
class AlertEvent:
    """A single alert occurrence with tracking metadata."""

    id: str
    severity: Severity
    title: str
    description: str
    source: str  # e.g. "health_check", "stripe_webhook", "latency_monitor"
    metadata: dict[str, Any] = field(default_factory=dict)
    status: AlertStatus = AlertStatus.FIRED
    fired_at: float = field(default_factory=time.time)
    acknowledged_at: float | None = None
    escalated_1_at: float | None = None
    escalated_2_at: float | None = None
    resolved_at: float | None = None


# ---------------------------------------------------------------------------
# In-memory alert registry (ephemeral — survives per-worker lifetime)
# In production, persistent state would live in Supabase or Redis.
# ---------------------------------------------------------------------------

_active_alerts: dict[str, AlertEvent] = {}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify(
    *,
    health_ready_fail_seconds: float = 0,
    ratio_5xx: float = 0,
    stripe_webhook_failure: bool = False,
    latency_p95_seconds: float = 0,
    redis_down_seconds: float = 0,
    api_quota_exhaustion: bool = False,
    cache_hit_ratio: float = 1.0,
    db_pool_ratio: float = 0,
    cron_delay_seconds: float = 0,
) -> Severity | None:
    """Determine severity from current system metrics.

    Returns the highest applicable severity, or ``None`` if all metrics
    are within normal ranges.

    Thresholds (AC1):
        SEV1 — backend DOWN (>60s /health/ready != 200), 5xx > 5%,
               Stripe webhook failure
        SEV2 — latency p95 > 2s, Redis DOWN > 5min, API quota exhaustion
        SEV3 — cache hit < 50%, DB pool > 85%, cron delayed > 1h
    """
    if health_ready_fail_seconds > SEV1_HEALTH_READY_FAIL_SECONDS:
        return Severity.SEV1
    if ratio_5xx > SEV1_5XX_RATIO:
        return Severity.SEV1
    if stripe_webhook_failure:
        return Severity.SEV1

    if latency_p95_seconds > SEV2_LATENCY_P95_SECONDS:
        return Severity.SEV2
    if redis_down_seconds > SEV2_REDIS_DOWN_SECONDS:
        return Severity.SEV2
    if api_quota_exhaustion:
        return Severity.SEV2

    if cache_hit_ratio < SEV3_CACHE_HIT_RATIO:
        return Severity.SEV3
    if db_pool_ratio > SEV3_DB_POOL_RATIO:
        return Severity.SEV3
    if cron_delay_seconds > SEV3_CRON_DELAY_SECONDS:
        return Severity.SEV3

    return None


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


async def _dispatch_pagerduty(event: AlertEvent) -> bool:
    """Send SEV1 alert to PagerDuty Events API v2.

    Returns True on success, False on failure (logged, never raises).
    Falls back gracefully if ``PAGERDUTY_ROUTING_KEY`` is unset.
    """
    routing_key = _PAGERDUTY_ROUTING_KEY
    if not routing_key:
        logger.debug("PAGERDUTY_ROUTING_KEY not set — skipping PagerDuty dispatch")
        return False

    payload = {
        "routing_key": routing_key,
        "event_action": "trigger",
        "payload": {
            "summary": event.title[:120],
            "severity": "critical",
            "source": event.source,
            "component": "smartlic-backend",
            "custom_details": {
                "id": event.id,
                "description": event.description[:500],
                "metadata": event.metadata,
            },
        },
        "dedup_key": f"smartlic:{event.id}",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
            )
            resp.raise_for_status()
        logger.info("PagerDuty alert sent for %s (%s)", event.id, event.title)
        return True
    except Exception as exc:
        logger.warning("PagerDuty dispatch failed for %s: %s", event.id, exc)
        return False


async def _dispatch_opsgenie(event: AlertEvent) -> bool:
    """Send SEV1 alert to Opsgenie (free-tier alternative to PagerDuty).

    Uses ``OPSGENIE_API_KEY`` and ``OPSGENIE_REGION`` env vars.
    Falls back gracefully if ``OPSGENIE_API_KEY`` is unset.
    """
    api_key = _OPSGENIE_API_KEY
    if not api_key:
        logger.debug("OPSGENIE_API_KEY not set — skipping Opsgenie dispatch")
        return False

    endpoint = (
        _OPSGENIE_EU_ENDPOINT
        if _OPSGENIE_REGION.lower() == "eu"
        else _OPSGENIE_US_ENDPOINT
    )

    payload = {
        "message": event.title[:130],
        "description": event.description[:15000],
        "source": event.source,
        "alias": f"smartlic:{event.id}",
        "priority": "P1",
        "tags": ["smartlic", event.severity.value, event.source],
        "details": {
            "id": event.id,
            "severity": event.severity.value,
            "metadata": str(event.metadata),
        },
    }

    headers = {
        "Authorization": f"GenieKey {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()
        logger.info("Opsgenie alert sent for %s (%s)", event.id, event.title)
        return True
    except Exception as exc:
        logger.warning("Opsgenie dispatch failed for %s: %s", event.id, exc)
        return False


async def _dispatch_slack(event: AlertEvent) -> bool:
    """Send alert to Slack ``#alerts`` channel.

    Uses the existing Slack webhook pattern from ``services/slack_notifier.py``.
    Configurable via ``SLACK_ALERTS_WEBHOOK_URL`` env var.

    When the webhook is not configured, falls back to sending via the
    ingestion Slack webhook (``SLACK_INGESTION_WEBHOOK_URL``) as a secondary
    channel.
    """
    webhook_url = _SLACK_ALERTS_WEBHOOK_URL

    # Fallback: reuse ingestion webhook if dedicated alerts webhook unset
    if not webhook_url:
        webhook_url = os.getenv("SLACK_INGESTION_WEBHOOK_URL", "")
        if not webhook_url:
            logger.debug(
                "SLACK_ALERTS_WEBHOOK_URL and SLACK_INGESTION_WEBHOOK_URL "
                "both unset — skipping Slack dispatch"
            )
            return False

    color = {
        Severity.SEV1: "danger",
        Severity.SEV2: "warning",
        Severity.SEV3: "good",
    }.get(event.severity, "danger")

    payload = {
        "text": (
            f":rotating_light: *[{event.severity.value}] {event.title}*"
        ),
        "attachments": [
            {
                "color": color,
                "fields": [
                    {"title": "Severity", "value": event.severity.value, "short": True},
                    {"title": "Source", "value": event.source, "short": True},
                    {"title": "Description", "value": event.description[:500], "short": False},
                ],
                "footer": "SmartLic Alert Manager",
                "ts": int(time.time()),
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()
        logger.info("Slack alert sent for %s (%s)", event.id, event.title)
        return True
    except Exception as exc:
        logger.warning("Slack dispatch failed for %s: %s", event.id, exc)
        return False


def _dispatch_sentry(event: AlertEvent) -> None:
    """Fire a Sentry event as universal fallback for all severities.

    Always runs regardless of other dispatch channels — ensures at least
    one observability trail exists.
    """
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("alert.severity", event.severity.value)
            scope.set_tag("alert.source", event.source)
            scope.set_tag("alert.id", event.id)
            scope.set_extra("metadata", event.metadata)
            scope.fingerprint = [
                "alert_manager",
                event.severity.value,
                event.source,
            ]
            sentry_sdk.capture_message(
                f"[{event.severity.value}] {event.title}",
                level={
                    Severity.SEV1: "fatal",
                    Severity.SEV2: "error",
                    Severity.SEV3: "warning",
                }.get(event.severity, "error"),
            )
    except Exception:
        logger.debug("sentry_sdk not available — skipping Sentry dispatch")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def fire_alert(
    title: str,
    description: str,
    source: str,
    severity: Severity | None = None,
    metadata: dict[str, Any] | None = None,
) -> AlertEvent:
    """Classify, create, and dispatch an alert.

    This is the primary entry point. Call it from health checks, cron
    monitors, webhook handlers, or the test-alert endpoint.

    Args:
        title: Short human-readable alert title.
        description: Detailed description (up to 500 chars in Slack fields).
        source: Identifier for the subsystem that raised the alert
                (e.g. ``health_check``, ``stripe_webhook``, ``latency_monitor``).
        severity: Optional explicit severity. If ``None``, classification
                  is skipped and the caller must have already determined it.
        metadata: Optional dict of extra context for debugging.

    Returns:
        The ``AlertEvent`` instance (id can be used for ack/escalation).
    """
    event = AlertEvent(
        id=_generate_alert_id(),
        severity=severity or Severity.SEV2,
        title=title,
        description=description,
        source=source,
        metadata=metadata or {},
    )

    _active_alerts[event.id] = event

    # Fire in parallel: PagerDuty/Opsgenie → Slack → Sentry (always)
    match event.severity:
        case Severity.SEV1:
            await _fire_sev1(event)
        case Severity.SEV2:
            await _fire_sev2(event)
        case Severity.SEV3:
            await _fire_sev3(event)

    logger.info(
        "Alert fired — id=%s severity=%s title=%s source=%s",
        event.id[:8],
        event.severity.value,
        event.title,
        event.source,
    )

    return event


async def _fire_sev1(event: AlertEvent) -> None:
    """SEV1: PagerDuty (or Opsgenie) + Slack + Sentry."""
    # Try PagerDuty first, fall back to Opsgenie
    pd_ok = await _dispatch_pagerduty(event)
    if not pd_ok:
        await _dispatch_opsgenie(event)
    await _dispatch_slack(event)
    _dispatch_sentry(event)


async def _fire_sev2(event: AlertEvent) -> None:
    """SEV2: Slack + Sentry."""
    await _dispatch_slack(event)
    _dispatch_sentry(event)


async def _fire_sev3(event: AlertEvent) -> None:
    """SEV3: Sentry only (collected for daily digest)."""
    _dispatch_sentry(event)


def acknowledge(alert_id: str) -> bool:
    """Mark a SEV1 alert as acknowledged, stopping escalation.

    Args:
        alert_id: The alert ID returned by :func:`fire_alert`.

    Returns:
        True if acknowledged, False if alert not found or already resolved.
    """
    event = _active_alerts.get(alert_id)
    if event is None or event.status in (AlertStatus.RESOLVED,):
        return False

    event.status = AlertStatus.ACKNOWLEDGED
    event.acknowledged_at = time.time()
    logger.info("Alert acknowledged — id=%s title=%s", alert_id[:8], event.title)
    return True


def resolve(alert_id: str, resolution_note: str = "") -> bool:
    """Mark an alert as resolved.

    Args:
        alert_id: The alert ID to resolve.
        resolution_note: Optional note about the resolution.

    Returns:
        True if resolved, False if not found.
    """
    event = _active_alerts.get(alert_id)
    if event is None:
        return False

    event.status = AlertStatus.RESOLVED
    event.resolved_at = time.time()
    if resolution_note:
        event.metadata["resolution_note"] = resolution_note
    logger.info(
        "Alert resolved — id=%s title=%s note=%s",
        alert_id[:8],
        event.title,
        resolution_note or "(none)",
    )
    return True


def get_active_alerts() -> list[AlertEvent]:
    """Return all currently active (non-resolved) alerts."""
    return [
        e for e in _active_alerts.values()
        if e.status != AlertStatus.RESOLVED
    ]


def get_alert(alert_id: str) -> AlertEvent | None:
    """Look up a specific alert by ID."""
    return _active_alerts.get(alert_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_alert_id() -> str:
    """Generate a unique alert ID using timestamp and counter."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    import random as _random
    rand = _random.randint(1000, 9999)
    return f"alrt-{ts}-{rand}"


# ---------------------------------------------------------------------------
# Escalation evaluation (called by jobs/cron/alert_escalation.py)
# ---------------------------------------------------------------------------


def check_escalation(now: float | None = None) -> list[AlertEvent]:
    """Check all SEV1 alerts and escalate if unacknowledged.

    Escalation policy (AC4):
        - SEV1 no ack within 5min → escalate to level 1 (Slack @here)
        - SEV1 no ack within 15min → escalate to level 2 (Slack @channel + Sentry fatal)

    Returns:
        List of alerts that were escalated during this check.
    """
    escalated: list[AlertEvent] = []
    now = now or time.time()

    for event in _active_alerts.values():
        if event.severity != Severity.SEV1:
            continue
        if event.status in (AlertStatus.RESOLVED, AlertStatus.ACKNOWLEDGED):
            continue

        elapsed = now - event.fired_at
        elapsed_minutes = elapsed / 60.0

        # Level 2 escalation (15 min)
        if (
            elapsed_minutes >= _SEV1_ESCALATION_MINUTES[1]
            and event.status != AlertStatus.ESCALATED_2
        ):
            event.status = AlertStatus.ESCALATED_2
            event.escalated_2_at = now
            escalated.append(event)
            logger.warning(
                "ESCALATION LEVEL 2 — alert %s (%s) unacknowledged for %.0f min",
                event.id[:8],
                event.title,
                elapsed_minutes,
            )

        # Level 1 escalation (5 min)
        elif (
            elapsed_minutes >= _SEV1_ESCALATION_MINUTES[0]
            and event.status not in (AlertStatus.ESCALATED_1, AlertStatus.ESCALATED_2)
        ):
            event.status = AlertStatus.ESCALATED_1
            event.escalated_1_at = now
            escalated.append(event)
            logger.warning(
                "ESCALATION LEVEL 1 — alert %s (%s) unacknowledged for %.0f min",
                event.id[:8],
                event.title,
                elapsed_minutes,
            )

    return escalated


def cleanup_stale_alerts(max_age_hours: int | None = None) -> int:
    """Remove resolved alerts older than *max_age_hours*.

    Args:
        max_age_hours: Alerts older than this are pruned. Defaults to
                       ``_ALERT_TTL_HOURS`` (48).

    Returns:
        Number of alerts removed.
    """
    if max_age_hours is None:
        max_age_hours = _ALERT_TTL_HOURS

    cutoff = time.time() - (max_age_hours * 3600)
    stale_ids = [
        eid
        for eid, event in _active_alerts.items()
        if event.status == AlertStatus.RESOLVED
        and (event.resolved_at or event.fired_at) < cutoff
    ]
    for eid in stale_ids:
        _active_alerts.pop(eid, None)

    if stale_ids:
        logger.info("Cleaned up %d stale alerts (age > %dh)", len(stale_ids), max_age_hours)
    return len(stale_ids)
