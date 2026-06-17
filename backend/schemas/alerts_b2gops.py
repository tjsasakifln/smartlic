"""B2GOPS-011 (#1281): Pydantic schemas for in-app user alerts.

Wave 1 of EPIC-B2GOPS (#1262) — Intelligent Alert System.
Defines request/response models for user_alerts CRUD, alert preferences,
and the alert generation engine.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Alert event types (mirrors SQL CHECK constraint)
# ---------------------------------------------------------------------------

ALERT_TYPES = frozenset({
    "new_matching_edital",
    "deadline_approaching",
    "pregao_starting",
    "result_published",
    "contrato_firmado",
    "documento_vencendo",
})


# ---------------------------------------------------------------------------
# Alert CRUD responses
# ---------------------------------------------------------------------------


class UserAlertResponse(BaseModel):
    """Single user alert record."""
    id: str
    user_id: str
    type: str
    title: str
    body: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    is_read: bool = False
    read_at: Optional[str] = None
    created_at: str


class UserAlertListResponse(BaseModel):
    """Paginated list of user alerts."""
    alerts: List[UserAlertResponse]
    total: int
    limit: int
    offset: int


class UnreadCountResponse(BaseModel):
    """Unread alert count for badge display."""
    unread_count: int


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------


class AlertPreferencesResponse(BaseModel):
    """User notification preferences."""
    channels: Dict[str, bool] = Field(
        default_factory=lambda: {"in_app": True},
        description="Enabled channels (e.g. in_app, email).",
    )
    enabled_types: List[str] = Field(
        default_factory=list,
        description="Whitelist of enabled alert types. Empty = all enabled.",
    )
    quiet_hours: Dict[str, Optional[str]] = Field(
        default_factory=lambda: {"start": None, "end": None},
        description="Quiet hours config (HH:MM format or null).",
    )


class UpdateAlertPreferencesRequest(BaseModel):
    """Partial update for alert preferences — all fields optional."""
    channels: Optional[Dict[str, bool]] = None
    enabled_types: Optional[List[str]] = None
    quiet_hours: Optional[Dict[str, Optional[str]]] = None


# ---------------------------------------------------------------------------
# Query params
# ---------------------------------------------------------------------------


class AlertQueryParams(BaseModel):
    """Query parameters for listing alerts."""
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    type: Optional[str] = Field(default=None, description="Filter by event type.")
    is_read: Optional[bool] = Field(default=None, description="Filter by read/unread status.")


# ---------------------------------------------------------------------------
# Alert engine schemas
# ---------------------------------------------------------------------------


class AlertEventPayload(BaseModel):
    """Payload for generating a new alert."""
    user_id: str
    type: str
    title: str
    body: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class AlertGenerationResult(BaseModel):
    """Result from alert generation engine."""
    generated: int = 0
    skipped: int = 0
    errors: int = 0
    details: List[str] = Field(default_factory=list)
