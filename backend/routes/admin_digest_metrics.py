"""
DIGEST-005 (#1421): Admin digest metrics endpoint.

Provides the admin dashboard widget with digest email performance metrics
over a 30-day rolling window, segmented by frequency (daily, twice_weekly,
weekly).

All data is queried from the ``email_tracking_events`` table (not Mixpanel),
so the dashboard works independently of external analytics providers.

Endpoint:
    GET /v1/admin/metrics/digest
"""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends

from admin import require_admin
from schemas.admin import AdminDigestMetricsResponse, DigestFrequencyBreakdown
from supabase_client import get_supabase, sb_execute

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])

VALID_FREQUENCIES = ("daily", "twice_weekly", "weekly")


@router.get(
    "/metrics/digest",
    response_model=AdminDigestMetricsResponse,
)
async def get_digest_metrics(
    user=Depends(require_admin),
) -> AdminDigestMetricsResponse:
    """Return digest email engagement metrics for the last 30 days.

    Rates computed:
      - open_rate_30d: opened / sent (as a float 0.0-1.0)
      - click_rate_30d: clicked / sent
      - unsubscribe_rate_30d: unsubscribed / sent
      - daily_avg_sent: total sent / 30

    Breakdown by frequency provides raw counts per frequency tier.
    Graceful degradation: if the table doesn't exist or the query fails,
    returns zeros.
    """
    queried_at = datetime.now(timezone.utc).isoformat()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    try:
        sb = get_supabase()

        # Fetch all tracking events from the last 30 days
        result = await sb_execute(
            sb.table("email_tracking_events")
            .select("event_type, digest_frequency")
            .gte("created_at", cutoff)
        )

        rows = result.data or []

        # Count totals
        total_sent = 0
        total_opened = 0
        total_clicked = 0
        total_unsubscribed = 0

        # Per-frequency breakdown
        freq_breakdown: dict[str, dict[str, int]] = {
            f: {"sent": 0, "opened": 0, "clicked": 0, "unsubscribed": 0}
            for f in VALID_FREQUENCIES
        }

        for row in rows:
            if not isinstance(row, dict):
                continue
            event_type = row.get("event_type", "")
            frequency = row.get("digest_frequency", "daily")

            if frequency not in VALID_FREQUENCIES:
                frequency = "daily"

            if event_type == "sent":
                total_sent += 1
                freq_breakdown[frequency]["sent"] += 1
            elif event_type == "opened":
                total_opened += 1
                freq_breakdown[frequency]["opened"] += 1
            elif event_type == "clicked":
                total_clicked += 1
                freq_breakdown[frequency]["clicked"] += 1
            elif event_type == "unsubscribed":
                total_unsubscribed += 1
                freq_breakdown[frequency]["unsubscribed"] += 1

        # Compute rates (avoid division by zero)
        open_rate = (
            round(total_opened / total_sent, 4) if total_sent > 0 else 0.0
        )
        click_rate = (
            round(total_clicked / total_sent, 4) if total_sent > 0 else 0.0
        )
        unsubscribe_rate = (
            round(total_unsubscribed / total_sent, 4) if total_sent > 0 else 0.0
        )
        daily_avg = round(total_sent / 30.0, 1)

        # Build frequency breakdown models
        breakdown = {
            freq: DigestFrequencyBreakdown(**counts)
            for freq, counts in freq_breakdown.items()
        }

        return AdminDigestMetricsResponse(
            daily_avg_sent=daily_avg,
            open_rate_30d=open_rate,
            click_rate_30d=click_rate,
            unsubscribe_rate_30d=unsubscribe_rate,
            total_sent_30d=total_sent,
            total_opened_30d=total_opened,
            total_clicked_30d=total_clicked,
            total_unsubscribed_30d=total_unsubscribed,
            breakdown_by_frequency=breakdown,
            queried_at=queried_at,
        )

    except Exception as exc:
        logger.warning("Failed to query digest metrics: %s", exc)
        return AdminDigestMetricsResponse(
            queried_at=queried_at,
        )
