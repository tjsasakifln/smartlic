"""Pydantic schemas for webhook integrations — B2GOPS-015 (#1522)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

__all__ = [
    "WebhookChannel",
    "WebhookEvent",
    "WebhookCreate",
    "WebhookUpdate",
    "WebhookResponse",
    "WebhookTestResponse",
]


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


class WebhookUpdate(BaseModel):
    """Request body for PATCH /v1/integrations/webhooks/{id}."""

    label: Optional[str] = None
    webhook_url: Optional[str] = None
    email_target: Optional[str] = None
    events: Optional[list[WebhookEvent]] = None
    is_active: Optional[bool] = None


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
