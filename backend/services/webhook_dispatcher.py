"""Webhook notification dispatcher — B2GOPS-015 (#1522).

Dispatches notifications to Slack, Microsoft Teams, and Email channels
with rate limiting (1 notification per event per hour).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

RATE_LIMIT_WINDOW = timedelta(hours=1)

# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


def _is_rate_limited(webhook: dict) -> bool:
    """Check if the webhook exceeds the 1-per-hour rate limit.

    Returns True if the last trigger was within the rate limit window.
    """
    last_triggered = webhook.get("last_triggered_at")
    if not last_triggered:
        return False
    if isinstance(last_triggered, str):
        last_triggered = datetime.fromisoformat(last_triggered.replace("Z", "+00:00"))
    age = datetime.now(timezone.utc) - last_triggered
    return age < RATE_LIMIT_WINDOW


async def _update_last_triggered(webhook_id: str) -> None:
    """Update last_triggered_at to now for the given webhook."""
    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        await sb_execute(
            sb.table("integrations_webhooks")
            .update({"last_triggered_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", webhook_id),
            category="write",
        )
    except Exception as exc:
        logger.warning("Failed to update last_triggered_at for webhook %s: %s", webhook_id[:8], exc)


# ---------------------------------------------------------------------------
# Message formatters
# ---------------------------------------------------------------------------


def _format_slack_message(event: str, payload: dict) -> dict:
    """Format a notification as a Slack incoming webhook message."""
    title = payload.get("title", "SmartLic Notification")
    description = payload.get("description", "")
    url = payload.get("url", "")
    color = payload.get("color", "#1E88E5")

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"📢 {title}"},
        },
    ]
    if description:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": description},
        })
    if url:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"<{url}|Abrir no SmartLic>",
            },
        })
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"Evento: `{event}` | SmartLic",
            }
        ],
    })

    return {
        "text": f"📢 {title}",
        "attachments": [
            {
                "color": color,
                "blocks": blocks,
            }
        ],
    }


def _format_teams_message(event: str, payload: dict) -> dict:
    """Format a notification as a Teams incoming webhook message (MessageCard)."""
    title = payload.get("title", "SmartLic Notification")
    description = payload.get("description", "")
    url = payload.get("url", "")

    sections = []
    if description:
        sections.append({
            "text": description,
        })
    if url:
        sections.append({
            "text": f"[Abrir no SmartLic]({url})",
        })

    return {
        "@type": "MessageCard",
        "@context": "https://schema.org/extensions",
        "summary": title,
        "title": f"📢 {title}",
        "sections": sections,
        "potentialAction": (
            [
                {
                    "@type": "OpenUri",
                    "name": "Abrir no SmartLic",
                    "targets": [{"os": "default", "uri": url}],
                }
            ]
            if url
            else []
        ),
    }


def _format_email_html(event: str, payload: dict) -> str:
    """Format a notification as HTML email body."""
    title = payload.get("title", "SmartLic Notification")
    description = payload.get("description", "")
    url = payload.get("url", "")

    rows = f"<p><strong>{title}</strong></p>"
    if description:
        rows += f"<p>{description}</p>"
    if url:
        rows += f'<p><a href="{url}" style="display:inline-block;padding:12px 24px;background-color:#1E88E5;color:#fff;text-decoration:none;border-radius:4px;">Abrir no SmartLic</a></p>'

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;">
    <div style="background-color:#f8f9fa;border-radius:8px;padding:24px;">
        {rows}
        <hr style="border:none;border-top:1px solid #e0e0e0;margin:16px 0;">
        <p style="font-size:12px;color:#666;">
            Evento: {event} | SmartLic
        </p>
    </div>
</body>
</html>"""


def _format_email_subject(event: str, payload: dict) -> str:
    """Format the email subject line."""
    title = payload.get("title", "SmartLic Notification")
    return f"📢 {title}"


# ---------------------------------------------------------------------------
# HTTP dispatchers
# ---------------------------------------------------------------------------


async def _send_webhook_post(url: str, json_data: dict) -> bool:
    """Send a POST request to a webhook URL. Returns True on success."""
    try:
        import httpx

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=json_data)
            resp.raise_for_status()
            return True
    except Exception as exc:
        logger.warning("Webhook POST failed to %s: %s", url[:50], exc)
        return False


async def _send_slack(webhook_url: str, event: str, payload: dict) -> bool:
    """Send notification to a Slack incoming webhook."""
    message = _format_slack_message(event, payload)
    return await _send_webhook_post(webhook_url, message)


async def _send_teams(webhook_url: str, event: str, payload: dict) -> bool:
    """Send notification to a Teams incoming webhook."""
    message = _format_teams_message(event, payload)
    return await _send_webhook_post(webhook_url, message)


async def _send_email(
    email_target: str, event: str, payload: dict
) -> bool:
    """Send notification via Resend email."""
    try:
        from email_service import send_email

        html = _format_email_html(event, payload)
        subject = _format_email_subject(event, payload)

        email_id = send_email(
            to=email_target,
            subject=subject,
            html=html,
            tags=[{"name": "category", "value": f"webhook:{event}"}],
        )
        if email_id:
            logger.info("Webhook email sent to %s: id=%s", email_target, email_id)
            return True
        logger.warning("Webhook email failed to send to %s", email_target)
        return False
    except Exception as exc:
        logger.warning("Webhook email exception for %s: %s", email_target, exc)
        return False


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------


async def dispatch_notification(
    webhook: dict, event: str, payload: dict
) -> bool:
    """Dispatch a notification to the configured webhook channel.

    Applies rate limiting: 1 notification per event per hour.
    Returns True if the notification was sent, False if rate-limited or failed.

    Args:
        webhook: Webhook config dict with keys: id, channel, webhook_url,
                 email_target, last_triggered_at, is_active.
        event: Event type string (e.g. 'new_edital', 'deadline_24h').
        payload: Dict with keys: title, description, url, color (optional).

    Returns:
        True if sent successfully, False otherwise.
    """
    if not webhook.get("is_active", True):
        logger.debug("Webhook %s is inactive — skipping", webhook.get("id", "")[:8])
        return False

    if _is_rate_limited(webhook):
        logger.info(
            "Webhook %s rate limited for event %s — skipping",
            webhook.get("id", "")[:8],
            event,
        )
        return False

    channel = webhook.get("channel", "")
    webhook_id = webhook.get("id", "")

    success = False
    if channel == "slack":
        success = await _send_slack(webhook.get("webhook_url", ""), event, payload)
    elif channel == "teams":
        success = await _send_teams(webhook.get("webhook_url", ""), event, payload)
    elif channel == "email":
        success = await _send_email(webhook.get("email_target", ""), event, payload)
    else:
        logger.warning("Unknown webhook channel: %s", channel)
        return False

    if success:
        await _update_last_triggered(webhook_id)

    return success
