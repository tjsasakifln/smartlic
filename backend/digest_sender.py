"""
DIGEST-003: Digest email sender -- Resend integration, List-Unsubscribe RFC 8058.

Builds digest email messages and sends them via email_service.send_email()
with proper List-Unsubscribe headers (RFC 8058, same pattern as alert emails).

Usage:
    from digest_sender import send_digest_email

    email_id = send_digest_email(
        user_email="user@example.com",
        user_name="Joao",
        opportunities=[...],
        frequency="daily",
        unsubscribe_token="abc123",
    )
"""

import logging
from typing import Optional

from templates.emails.digest import render_digest_email, get_digest_subject
from email_service import send_email
from templates.emails.base import FRONTEND_URL

logger = logging.getLogger(__name__)

# Tag prefix for Resend categorization
DIGEST_TAG_CATEGORY = "digest"


def send_digest_email(
    user_email: str,
    user_name: str,
    opportunities: list[dict],
    frequency: str = "daily",
    unsubscribe_token: str = "",
) -> Optional[str]:
    """Send a digest email via Resend with List-Unsubscribe headers.

    DIGEST-003: Integrates with email_service.send_email(), adds
    RFC 8058 List-Unsubscribe and List-Unsubscribe-Post headers
    matching the same pattern used by alert emails.

    Args:
        user_email: Recipient email address.
        user_name: User's display name.
        opportunities: List of opportunity dicts with keys:
            titulo, orgao, valor_estimado, uf, viability_score.
        frequency: "daily" or "weekly".
        unsubscribe_token: Token for one-click unsubscribe URL.

    Returns:
        Resend email ID string on success, None on failure.
    """
    # Build subject line
    total_count = len(opportunities)
    subject = get_digest_subject(total_count, frequency)

    # Render HTML template
    html = render_digest_email(
        user_name=user_name,
        opportunities=opportunities,
        frequency=frequency,
        unsubscribe_token=unsubscribe_token,
    )

    # Build List-Unsubscribe headers (RFC 8058, same pattern as alert emails)
    headers: dict[str, str] = {}
    if unsubscribe_token:
        unsubscribe_url = f"{FRONTEND_URL}/conta/preferencias?unsubscribe={unsubscribe_token}"
        headers = {
            "List-Unsubscribe": f"<{unsubscribe_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }

    # Build Resend tags for tracking
    tags = [
        {"name": "category", "value": DIGEST_TAG_CATEGORY},
        {"name": "frequency", "value": frequency},
    ]

    # Send via email_service
    email_id = send_email(
        to=user_email,
        subject=subject,
        html=html,
        headers=headers,
        tags=tags,
    )

    if email_id:
        logger.info(
            "Digest email sent: to=%s, subject=%s, frequency=%s, id=%s",
            user_email,
            subject,
            frequency,
            email_id,
        )
    else:
        logger.warning(
            "Digest email failed to send: to=%s, subject=%s, frequency=%s",
            user_email,
            subject,
            frequency,
        )

    return email_id
