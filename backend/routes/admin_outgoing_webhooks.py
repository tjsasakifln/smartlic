"""Issue #1959: Outgoing webhook deliveries admin endpoints.

Endpoints (all admin-only):
    GET /v1/admin/webhook-deliveries — list deliveries with optional filters

Every endpoint degrades gracefully: Supabase unavailability returns a
structured error response instead of 500-ing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from supabase_client import get_supabase, sb_execute

from admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "webhooks"])


# ---------------------------------------------------------------------------
# GET /v1/admin/webhook-deliveries
# ---------------------------------------------------------------------------


@router.get("/webhook-deliveries", response_model=dict)
async def get_webhook_deliveries(
    status: str | None = Query(None, description="Filter by status: pending, delivered, failed, cancelled"),
    channel: str | None = Query(None, description="Filter by channel: slack, teams, email"),
    limit: int = Query(50, ge=1, le=500, description="Max entries to return"),
    user=Depends(require_admin),
) -> dict[str, Any]:
    """List outgoing webhook deliveries.

    Supports optional filtering by ``status`` and/or ``channel``.
    Results are sorted by ``created_at`` descending (most recent first).

    Returns::

        {
            "status": "ok",
            "queried_at": "2026-06-17T12:00:00+00:00",
            "count": N,
            "entries": [...]
        }

    When Supabase is unreachable the response carries ``status="error"``
    and an empty ``entries`` list.
    """
    queried_at = datetime.now(timezone.utc).isoformat()

    try:
        db = get_supabase()
        query = (
            db.table("outgoing_webhook_deliveries")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )

        if status:
            query = query.eq("status", status)
        if channel:
            query = query.eq("channel", channel)

        result = await sb_execute(query.execute(), category="read")
        entries = result.data if result.data else []

        return {
            "status": "ok",
            "queried_at": queried_at,
            "count": len(entries),
            "entries": entries,
        }

    except Exception as exc:
        logger.warning("GET /v1/admin/webhook-deliveries failed: %s", exc)
        return {
            "status": "error",
            "queried_at": queried_at,
            "count": 0,
            "entries": [],
            "detail": str(exc),
        }
