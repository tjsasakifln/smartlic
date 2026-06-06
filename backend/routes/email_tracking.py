"""
DIGEST-005 (#1421): Email open/click/unsubscribe tracking routes.

Provides endpoints for tracking digest email engagement via:
- Tracking pixel (1x1 transparent GIF) for open detection
- Click tracking redirect (302) for CTA clicks
- Unsubscribe tracking with Mixpanel event

All endpoints store events in ``email_tracking_events`` table so the admin
dashboard widget can query metrics directly (no Mixpanel dependency for
aggregates).

Mixpanel events are fired fire-and-forget for:
  - digest_opened
  - digest_clicked
  - digest_unsubscribe
"""

import base64
import logging
import os

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse, Response
from pydantic import BaseModel

from analytics_events import track_event
from supabase_client import get_supabase, sb_execute

logger = logging.getLogger(__name__)

router = APIRouter(tags=["email_tracking"])

BACKEND_URL = os.getenv("BACKEND_URL", "https://smartlic-backend-production.up.railway.app")

# 1x1 transparent GIF (43 bytes) — base64-decoded once at module load
_TRACKING_PIXEL = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


# ============================================================================
# Request/response schemas
# ============================================================================

class TrackSentRequest(BaseModel):
    """Payload for POST /api/email/track-sent."""
    tracking_id: str
    user_id: str
    frequency: str = "daily"
    opportunity_count: int = 0
    sectors: list[str] = []


class TrackSentResponse(BaseModel):
    status: str
    tracking_id: str


class UnsubscribeRequest(BaseModel):
    """Payload for POST /api/email/unsubscribe."""
    user_id: str
    tracking_id: str
    frequency: str = "daily"


class UnsubscribeResponse(BaseModel):
    status: str
    message: str


# ============================================================================
# Helper: insert a tracking event into the DB
# ============================================================================

async def _insert_tracking_event(
    tracking_id: str,
    event_type: str,
    user_id: str | None = None,
    frequency: str = "daily",
    metadata: dict | None = None,
) -> None:
    """Insert a row into email_tracking_events.

    Fire-and-forget: never raises. Logs warnings on failure.
    """
    try:
        sb = get_supabase()
        await sb_execute(sb.table("email_tracking_events").insert({
            "tracking_id": tracking_id,
            "event_type": event_type,
            "user_id": user_id,
            "digest_frequency": frequency,
            "metadata": metadata or {},
        }))
    except Exception as e:
        logger.warning(
            "Failed to insert tracking event (type=%s, tracking=%s): %s",
            event_type, tracking_id[:8], e,
        )


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/api/email/open/{tracking_id}",
    response_class=Response,
    response_model=None,
)
async def track_email_open(tracking_id: str):
    """Tracking pixel endpoint — fires ``digest_opened`` Mixpanel event.

    Returns a 1x1 transparent GIF (43 bytes). Inserts an ``opened`` event
    into ``email_tracking_events`` and fires a fire-and-forget Mixpanel
    ``digest_opened`` event.

    Called via ``<img>`` tag in the email HTML. Since email clients cache
    images aggressively, this is a best-effort metric.
    """
    try:
        # Try to look up the original sent event for user & frequency metadata
        user_id: str | None = None
        frequency: str = "daily"

        try:
            sb = get_supabase()
            sent_event = await sb_execute(
                sb.table("email_tracking_events")
                .select("user_id, digest_frequency")
                .eq("tracking_id", tracking_id)
                .eq("event_type", "sent")
                .limit(1)
            )
            if sent_event and sent_event.data:
                row = sent_event.data[0]
                user_id = row.get("user_id")
                frequency = row.get("digest_frequency", "daily")
        except Exception:
            pass  # Best effort — tracking still works without lookup

        # Insert opened event
        await _insert_tracking_event(
            tracking_id=tracking_id,
            event_type="opened",
            user_id=user_id,
            frequency=frequency,
        )

        # Fire Mixpanel event (fire-and-forget)
        track_event("digest_opened", {
            "tracking_id": tracking_id,
            "user_id": user_id or "unknown",
            "frequency": frequency,
        })

    except Exception:
        pass  # Never fail the pixel — email clients won't retry

    # Return 1x1 transparent GIF
    return Response(
        content=_TRACKING_PIXEL,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/api/email/click/{tracking_id}", response_model=None)
async def track_email_click(
    tracking_id: str,
    url: str = Query(..., description="Target URL to redirect to"),
):
    """Click tracking endpoint — fires ``digest_clicked`` Mixpanel event.

    Records a ``clicked`` event in ``email_tracking_events``, fires a
    fire-and-forget Mixpanel ``digest_clicked`` event, then redirects the
    user to the target URL via 302.

    Args:
        tracking_id: UUID tracking identifier from email HTML.
        url: Target URL (must be a valid smartlic.tech URL).
    """
    # Validate URL — only allow smartlic.tech URLs for security
    if not url.startswith("https://smartlic.tech") and not url.startswith("http://localhost:"):
        logger.warning("Blocked click tracking to non-smartlic URL: %s", url[:60])
        return RedirectResponse(
            url="https://smartlic.tech",
            status_code=302,
        )

    try:
        # Look up sent event for user context
        user_id: str | None = None
        frequency: str = "daily"

        try:
            sb = get_supabase()
            sent_event = await sb_execute(
                sb.table("email_tracking_events")
                .select("user_id, digest_frequency")
                .eq("tracking_id", tracking_id)
                .eq("event_type", "sent")
                .limit(1)
            )
            if sent_event and sent_event.data:
                row = sent_event.data[0]
                user_id = row.get("user_id")
                frequency = row.get("digest_frequency", "daily")
        except Exception:
            pass

        # Insert clicked event
        await _insert_tracking_event(
            tracking_id=tracking_id,
            event_type="clicked",
            user_id=user_id,
            frequency=frequency,
            metadata={"target_url": url},
        )

        # Fire Mixpanel event (fire-and-forget)
        track_event("digest_clicked", {
            "tracking_id": tracking_id,
            "user_id": user_id or "unknown",
            "frequency": frequency,
            "target_url": url,
        })

    except Exception:
        pass  # Never block the redirect

    return RedirectResponse(url=url, status_code=302)


@router.post(
    "/api/email/track-sent",
    response_model=TrackSentResponse,
)
async def track_digest_sent(payload: TrackSentRequest):
    """Record a ``sent`` event after a digest email is successfully delivered.

    Called by the digest sender after Resend confirms delivery. Inserts a row
    into ``email_tracking_events`` so the admin dashboard can count sent
    digests per day.

    The tracking_id is generated by the digest sender and embedded in the
    email HTML for open/click tracking correlation.
    """
    tracking_id = payload.tracking_id

    await _insert_tracking_event(
        tracking_id=tracking_id,
        event_type="sent",
        user_id=payload.user_id,
        frequency=payload.frequency,
        metadata={
            "opportunity_count": payload.opportunity_count,
            "sectors": payload.sectors,
        },
    )

    # Fire Mixpanel event (fire-and-forget) — already fired by sender,
    # but fire here too as a backup in case the sender somehow missed it.
    track_event("digest_sent", {
        "tracking_id": tracking_id,
        "user_id": payload.user_id,
        "frequency": payload.frequency,
        "opportunity_count": payload.opportunity_count,
        "sectors": ",".join(payload.sectors),
    })

    logger.info(
        "Digest sent tracked: user=%s, freq=%s, opps=%d",
        payload.user_id[:8], payload.frequency, payload.opportunity_count,
    )

    return TrackSentResponse(status="ok", tracking_id=tracking_id)


@router.post(
    "/api/email/unsubscribe",
    response_model=UnsubscribeResponse,
)
async def track_email_unsubscribe(payload: UnsubscribeRequest):
    """Unsubscribe from digest emails — fires ``digest_unsubscribe`` Mixpanel event.

    Records an ``unsubscribed`` event in ``email_tracking_events`` and fires
    a fire-and-forget Mixpanel ``digest_unsubscribe`` event.
    """
    await _insert_tracking_event(
        tracking_id=payload.tracking_id,
        event_type="unsubscribed",
        user_id=payload.user_id,
        frequency=payload.frequency,
    )

    # Fire Mixpanel event (fire-and-forget)
    track_event("digest_unsubscribe", {
        "tracking_id": payload.tracking_id,
        "user_id": payload.user_id,
        "frequency": payload.frequency,
    })

    logger.info(
        "Digest unsubscribe tracked: user=%s, freq=%s",
        payload.user_id[:8], payload.frequency,
    )

    return UnsubscribeResponse(
        status="ok",
        message="Unsubscribe tracked successfully",
    )
