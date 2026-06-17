"""Pydantic schemas for webhook integrations — B2GOPS-015 (#1522).

SSRF hardening: webhook_url fields enforce HTTPS-only + block internal/private
IPs via custom field_validator. See security/SSRF-001.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

# Hosts that are never allowed as webhook targets (SSRF prevention).
# Covers localhost, loopback, cloud metadata endpoints, and common
# private IP ranges checked at parse time.
_BLOCKED_SSRF_HOSTS: set[str] = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",  # AWS/GCP/Azure metadata
    "metadata.google.internal",  # GCP metadata
    "100.100.100.200",  # Alicloud metadata
}

__all__ = [
    "WebhookChannel",
    "WebhookEvent",
    "WebhookCreate",
    "WebhookUpdate",
    "WebhookResponse",
    "WebhookTestResponse",
    "validate_webhook_url",
]


def validate_webhook_url(v: Optional[str]) -> Optional[str]:
    """Validate a webhook URL for SSRF safety.

    Checks performed:
    1. None is always allowed (field is optional).
    2. Must be HTTPS (not HTTP or other schemes).
    3. Hostname must not be in the blocked-SSRF set.
    4. Hostname must not be a private/reserved IP (10.x, 172.16-31.x,
       192.168.x, 127.x.x.x).

    Returns the original value (passthrough) if valid, raises ValueError
    with a specific message otherwise.
    """
    if v is None:
        return v

    parsed = urlparse(v)

    # Scheme enforcement -- only HTTPS is safe for webhooks
    if parsed.scheme != "https":
        raise ValueError(
            f"Webhook URL scheme must be 'https', got '{parsed.scheme}'"
        )

    hostname = (parsed.hostname or "").lower()

    # Block known internal/metadata hosts
    if hostname in _BLOCKED_SSRF_HOSTS:
        raise ValueError(
            f"Webhook URL host not allowed: {hostname}"
        )

    # Block private/reserved IP ranges
    if hostname.startswith("10.") or hostname.startswith("192.168."):
        raise ValueError(
            f"Webhook URL host is a private IP range: {hostname}"
        )

    # 172.16.0.0 - 172.31.255.255
    # The try/except only guards the int() parsing of the second octet;
    # the ValueError for private range is raised OUTSIDE the handler so
    # it is not accidentally swallowed.
    if hostname.startswith("172."):
        try:
            second_octet = int(hostname.split(".")[1])
        except (IndexError, ValueError):
            second_octet = -1
        if 16 <= second_octet <= 31:
            raise ValueError(
                f"Webhook URL host is a private IP range: {hostname}"
            )

    # Block link-local (169.254.x.x)
    if hostname.startswith("169.254."):
        raise ValueError(
            f"Webhook URL host is a link-local address: {hostname}"
        )

    return v


class WebhookChannel(str, Enum):
    """Supported notification channels."""

    slack = "slack"
    teams = "teams"
    email = "email"


class WebhookEvent(str, Enum):
    """Notification event types for webhook dispatch."""

    new_edital = "new_edital"
    deadline_24h = "deadline_24h"
    deadline_6h = "deadline_6h"
    deadline_1h = "deadline_1h"
    pregao_started = "pregao_started"
    result_published = "result_published"


class WebhookCreate(BaseModel):
    """Request body for POST /v1/integrations/webhooks."""

    channel: WebhookChannel
    label: Optional[str] = None
    webhook_url: Optional[str] = Field(None, description="Incoming webhook URL (required for slack/teams)")
    email_target: Optional[str] = Field(None, description="Email address (required for email channel)")
    events: list[WebhookEvent] = []

    _validate_webhook_url = field_validator("webhook_url")(validate_webhook_url)


class WebhookUpdate(BaseModel):
    """Request body for PATCH /v1/integrations/webhooks/{id}."""

    label: Optional[str] = None
    webhook_url: Optional[str] = None
    email_target: Optional[str] = None
    events: Optional[list[WebhookEvent]] = None
    is_active: Optional[bool] = None

    _validate_webhook_url = field_validator("webhook_url")(validate_webhook_url)


class WebhookResponse(BaseModel):
    """Public webhook representation returned by the API."""

    id: str
    channel: WebhookChannel
    label: Optional[str] = None
    webhook_url: Optional[str] = None
    email_target: Optional[str] = None
    events: list[WebhookEvent]
    is_active: bool
    last_triggered_at: Optional[datetime] = None
    created_at: datetime


class WebhookTestResponse(BaseModel):
    """Response from the test notification endpoint."""

    message: str
    channel: WebhookChannel
    target: Optional[str] = None
