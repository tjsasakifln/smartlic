"""NETINT-014 (#1519): IntelFeed schemas for EmbedIntelFeed widget.

Models for the compact market intelligence feed shown on SEO programmatic pages.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class IntelFeedSignal(BaseModel):
    """Single market signal displayed in the widget."""

    label: str
    value: str
    trend: Optional[str] = None  # "up" | "down" | "stable"


class IntelFeedResponse(BaseModel):
    """Full response payload for the intel feed endpoint."""

    sector: str
    signals: list[IntelFeedSignal]
    generated_at: datetime
