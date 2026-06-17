"""#1865 AC7: Test alert endpoint — POST /v1/admin/test-alert.

Fires a real alert through the full dispatch pipeline (PagerDuty/Opsgenie
→ Slack → Sentry) for verification.

Usage:
    curl -X POST https://smartlic.tech/v1/admin/test-alert \\
      -H "Authorization: Bearer <admin-token>" \\
      -H "Content-Type: application/json" \\
      -d '{"severity": "SEV1", "title": "Test alert — ignore"}'
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from admin import require_admin_ops
from services.alert_manager import Severity, fire_alert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "alerts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TestAlertRequest(BaseModel):
    """Request payload for the test-alert endpoint."""

    severity: Severity = Field(
        default=Severity.SEV2,
        description="Severity tier to test (SEV1, SEV2, or SEV3).",
    )
    title: str = Field(
        default="Test alert from admin",
        min_length=1,
        max_length=200,
        description="Short alert title.",
    )


class TestAlertResponse(BaseModel):
    """Response returned after dispatching a test alert."""

    alert_id: str
    severity: str
    title: str
    dispatched_at: float
    message: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/test-alert", response_model=TestAlertResponse)
async def trigger_test_alert(
    req: TestAlertRequest,
    user: dict = Depends(require_admin_ops),
) -> TestAlertResponse:
    """Fire a real alert through the full dispatch pipeline.

    This endpoint exists for verification purposes (AC7). It dispatches
    an alert with the given severity and title, exercising PagerDuty/
    Opsgenie integration (SEV1), Slack webhook (SEV1/SEV2), and Sentry
    capture (all tiers).

    The caller must be authenticated as an admin user.
    """
    actor_email = user.get("email", "admin@unknown")
    logger.info(
        "Test alert triggered by %s — severity=%s title=%s",
        actor_email,
        req.severity.value,
        req.title,
    )

    event = await fire_alert(
        title=req.title,
        description=(
            f"Test alert triggered by admin {actor_email} at "
            f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}. "
            f"This is a synthetic test — no action required."
        ),
        source="test_alert_admin",
        severity=req.severity,
        metadata={"triggered_by": actor_email, "test": True},
    )

    return TestAlertResponse(
        alert_id=event.id,
        severity=event.severity.value,
        title=event.title,
        dispatched_at=event.fired_at,
        message=f"Test alert dispatched via {event.severity.value} pipeline.",
    )
