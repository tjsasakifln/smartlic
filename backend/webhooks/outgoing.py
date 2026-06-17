"""Outgoing webhook delivery with exponential backoff.

Issue #1959: Async delivery of Slack/Teams/Email webhooks with retry logic.
Deliveries are tracked in the ``outgoing_webhook_deliveries`` table for
observability and idempotency.

Usage::

    from webhooks.outgoing import enqueue_webhook, deliver_webhook

    # Enqueue a webhook delivery (creates DB record, ARQ picks it up)
    await enqueue_webhook(
        channel="slack",
        event_type="trial_expiring",
        entity_id="user_abc123",
        payload={"user_id": "abc", "days_left": 3},
    )

    # Direct delivery (bypasses queue, used by ARQ job)
    result = await deliver_webhook(webhook_url, payload, channel)
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# ============================================================================
# Exponential backoff schedule (seconds)
# Retry 0 -> 1s, retry 1 -> 5s, retry 2 -> 25s (max 3 retries = 4 total
# attempts including initial delivery that already happened).
# ============================================================================
BACKOFF_DELAYS: list[int] = [1, 5, 25]
MAX_RETRIES: int = len(BACKOFF_DELAYS)  # 3
DELIVERY_TIMEOUT_S: float = 10.0


def get_next_retry_at(retries: int) -> datetime | None:
    """Calculate next retry time using exponential backoff.

    Args:
        retries: Current number of failed attempts.

    Returns:
        UTC datetime for next retry, or None if max retries exhausted.
    """
    if retries >= MAX_RETRIES:
        return None
    delay = BACKOFF_DELAYS[retries]
    return datetime.now(timezone.utc) + timedelta(seconds=delay)


def _get_webhook_url(channel: str) -> str:
    """Retrieve webhook URL for the given channel from environment variables.

    Args:
        channel: Delivery channel ('slack', 'teams', 'email').

    Returns:
        Webhook URL string.

    Raises:
        ValueError: If the channel's webhook URL is not configured.
    """
    import os

    env_var = f"WEBHOOK_URL_{channel.upper()}"
    url = os.getenv(env_var, "")
    if not url:
        raise ValueError(
            f"Webhook URL not configured: set {env_var} environment variable"
        )
    return url


async def deliver_webhook(
    webhook_url: str,
    payload: dict[str, Any],
    channel: str,
) -> dict[str, Any]:
    """Deliver a webhook payload to the target URL.

    Args:
        webhook_url: Target webhook URL.
        payload: JSON-serializable payload to deliver.
        channel: Delivery channel name (for logging/metrics).

    Returns:
        Dict with ``status`` ("delivered" or "failed"), ``status_code``,
        and optional ``error`` message.
    """
    try:
        async with httpx.AsyncClient(timeout=DELIVERY_TIMEOUT_S) as client:
            response = await client.post(webhook_url, json=payload)
            # 2xx/3xx/4xx are considered delivered (4xx = bad request, not retryable)
            if response.status_code < 500:
                logger.info(
                    "Webhook delivered to %s channel (status=%d)",
                    channel, response.status_code,
                )
                return {
                    "status": "delivered",
                    "status_code": response.status_code,
                }

            # 5xx = server error, retryable
            logger.warning(
                "Webhook %s returned %d: %s",
                channel, response.status_code, response.text[:200],
            )
            return {
                "status": "failed",
                "status_code": response.status_code,
                "error": response.text[:500],
            }

    except httpx.TimeoutException as exc:
        logger.warning("Webhook %s timeout: %s", channel, exc)
        return {"status": "failed", "error": f"Timeout: {exc}"}

    except httpx.RequestError as exc:
        logger.warning("Webhook %s request error: %s", channel, exc)
        return {"status": "failed", "error": f"RequestError: {exc}"}


# Lazy import of httpx to avoid circular imports at module level
import httpx  # noqa: E402


async def enqueue_webhook(
    channel: str,
    event_type: str,
    entity_id: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enqueue a webhook delivery by inserting a record in the delivery table.

    Idempotency: if a delivery with the same (channel, event_type, entity_id)
    already exists with status 'delivered', the operation is skipped silently.

    Args:
        channel: Delivery channel ('slack', 'teams', 'email').
        event_type: Event type identifier.
        entity_id: Entity ID associated with the event.
        payload: JSON payload to deliver (default empty dict).

    Returns:
        Dict with ``status`` ("ok", "skipped", or "error"), ``id`` (UUID),
        and optional ``detail``.
    """
    from supabase_client import get_supabase, sb_execute

    payload = payload or {}
    db = get_supabase()

    # Idempotency check: skip if already delivered
    try:
        existing = await sb_execute(
            db.table("outgoing_webhook_deliveries")
            .select("id, status")
            .eq("channel", channel)
            .eq("event_type", event_type)
            .eq("entity_id", entity_id)
            .maybe_single(),
            category="read",
        )
        if existing and hasattr(existing, "data") and existing.data:
            row = existing.data
            if row.get("status") == "delivered":
                logger.info(
                    "Webhook already delivered: %s/%s/%s",
                    channel, event_type, entity_id,
                )
                return {
                    "status": "skipped",
                    "id": str(row["id"]),
                    "detail": "Already delivered (idempotency)",
                }
    except Exception as exc:
        logger.warning("Idempotency check failed (proceeding): %s", exc)

    # Create delivery record
    now = datetime.now(timezone.utc)
    next_retry_at = get_next_retry_at(0)  # First retry scheduled

    try:
        result = await sb_execute(
            db.table("outgoing_webhook_deliveries")
            .insert({
                "channel": channel,
                "event_type": event_type,
                "entity_id": entity_id,
                "payload": payload,
                "status": "pending",
                "retries": 0,
                "max_retries": MAX_RETRIES,
                "next_retry_at": next_retry_at.isoformat() if next_retry_at else None,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
            .execute(),
            category="write",
        )
        record_id = result.data[0]["id"] if result.data else None
        logger.info(
            "Webhook enqueued: %s/%s/%s (id=%s)",
            channel, event_type, entity_id, record_id,
        )
        return {"status": "ok", "id": str(record_id) if record_id else ""}

    except Exception as exc:
        # Check for unique violation — duplicate (channel, event_type, entity_id)
        error_str = str(exc)
        if "duplicate key" in error_str.lower() or "unique" in error_str.lower():
            logger.info(
                "Webhook already pending: %s/%s/%s",
                channel, event_type, entity_id,
            )
            return {
                "status": "skipped",
                "detail": "Already exists (duplicate key)",
            }
        logger.error("Failed to enqueue webhook: %s", exc)
        return {"status": "error", "detail": str(exc)}


async def process_pending_deliveries(limit: int = 50) -> dict[str, Any]:
    """Process pending webhook deliveries.

    Called by the ARQ ``send_outgoing_webhook`` job. Queries pending deliveries
    whose ``next_retry_at <= now()``, attempts delivery, and updates status.

    Args:
        limit: Maximum number of pending deliveries to process (default 50).

    Returns:
        Dict with summary: ``processed``, ``delivered``, ``failed``, ``exhausted``.
    """
    from supabase_client import get_supabase, sb_execute

    db = get_supabase()
    now = datetime.now(timezone.utc)

    # Fetch pending deliveries ready for retry
    try:
        result = await sb_execute(
            db.table("outgoing_webhook_deliveries")
            .select("*")
            .eq("status", "pending")
            .lte("next_retry_at", now.isoformat())
            .order("next_retry_at")
            .limit(limit)
            .execute(),
            category="read",
        )
    except Exception as exc:
        logger.error("Failed to query pending deliveries: %s", exc)
        return {"processed": 0, "delivered": 0, "failed": 0, "exhausted": 0, "error": str(exc)}

    rows = result.data if result.data else []
    if not rows:
        logger.debug("No pending webhook deliveries to process")
        return {"processed": 0, "delivered": 0, "failed": 0, "exhausted": 0}

    summary = {"processed": 0, "delivered": 0, "failed": 0, "exhausted": 0}

    for row in rows:
        record_id = row["id"]
        channel = row["channel"]
        event_type = row.get("event_type", "")
        entity_id = row.get("entity_id", "")
        payload = row.get("payload", {}) or {}
        retries = row.get("retries", 0)

        summary["processed"] += 1

        try:
            # Get webhook URL and deliver
            webhook_url = _get_webhook_url(channel)
            delivery_result = await deliver_webhook(webhook_url, payload, channel)

            if delivery_result.get("status") == "delivered":
                # Mark as delivered
                await sb_execute(
                    db.table("outgoing_webhook_deliveries")
                    .update({
                        "status": "delivered",
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    })
                    .eq("id", record_id)
                    .execute(),
                    category="write",
                )
                summary["delivered"] += 1

                # Track metrics
                try:
                    from metrics import WEBHOOK_OUTGOING_TOTAL
                    WEBHOOK_OUTGOING_TOTAL.labels(channel=channel, status="delivered").inc()
                except Exception:
                    pass

                logger.info(
                    "Webhook %s/%s/%s delivered after %d retries",
                    channel, event_type, entity_id, retries,
                )
            else:
                # Failed — increment retries, schedule next attempt or mark failed
                new_retries = retries + 1
                next_retry = get_next_retry_at(new_retries)

                if next_retry is None:
                    # Exhausted all retries
                    await sb_execute(
                        db.table("outgoing_webhook_deliveries")
                        .update({
                            "status": "failed",
                            "retries": new_retries,
                            "last_error": delivery_result.get("error", "Max retries exhausted"),
                            "next_retry_at": None,
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        })
                        .eq("id", record_id)
                        .execute(),
                        category="write",
                    )
                    summary["exhausted"] += 1
                    summary["failed"] += 1

                    try:
                        from metrics import WEBHOOK_OUTGOING_TOTAL
                        WEBHOOK_OUTGOING_TOTAL.labels(channel=channel, status="failed").inc()
                        from metrics import WEBHOOK_OUTGOING_RETRIES_TOTAL
                        WEBHOOK_OUTGOING_RETRIES_TOTAL.labels(channel=channel).inc()
                    except Exception:
                        pass

                    # Sentry alert: rate(smartlic_webhook_outgoing_total{status="failed"}[10m]) > 0
                    try:
                        import sentry_sdk
                        sentry_sdk.capture_message(
                            f"Webhook delivery failed after {new_retries} retries: "
                            f"{channel}/{event_type}/{entity_id} — {delivery_result.get('error', '')}",
                            level="warning",
                        )
                    except Exception:
                        pass

                    logger.warning(
                        "Webhook %s/%s/%s failed after %d retries: %s",
                        channel, event_type, entity_id, new_retries,
                        delivery_result.get("error", ""),
                    )
                else:
                    # Schedule next retry
                    await sb_execute(
                        db.table("outgoing_webhook_deliveries")
                        .update({
                            "retries": new_retries,
                            "last_error": delivery_result.get("error", ""),
                            "next_retry_at": next_retry.isoformat(),
                            "updated_at": datetime.now(timezone.utc).isoformat(),
                        })
                        .eq("id", record_id)
                        .execute(),
                        category="write",
                    )
                    summary["failed"] += 1

                    # Track retry metric
                    try:
                        from metrics import WEBHOOK_OUTGOING_RETRIES_TOTAL
                        WEBHOOK_OUTGOING_RETRIES_TOTAL.labels(channel=channel).inc()
                    except Exception:
                        pass

                    logger.info(
                        "Webhook %s/%s/%s retry %d/%d scheduled at %s",
                        channel, event_type, entity_id,
                        new_retries, MAX_RETRIES, next_retry.isoformat(),
                    )

        except ValueError as exc:
            # Webhook URL not configured
            logger.warning(
                "Webhook %s/%s/%s skipped: %s",
                channel, event_type, entity_id, exc,
            )
            # Mark as failed with configuration error
            try:
                await sb_execute(
                    db.table("outgoing_webhook_deliveries")
                    .update({
                        "status": "failed",
                        "last_error": str(exc),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    })
                    .eq("id", record_id)
                    .execute(),
                    category="write",
                )
            except Exception:
                pass
            summary["failed"] += 1

        except Exception as exc:
            logger.error(
                "Unexpected error processing webhook %s: %s",
                record_id, exc,
            )
            summary["failed"] += 1

    return summary
