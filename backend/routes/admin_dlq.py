"""Issue #1813: ARQ Dead Letter Queue admin endpoints.

Endpoints (all admin-only):
    GET    /v1/admin/dlq           — list DLQ entries
    POST   /v1/admin/dlq/{uuid}/retry  — re-enqueue a DLQ entry to ARQ
    DELETE /v1/admin/dlq           — purge all DLQ entries

Every endpoint degrades gracefully: Redis/ARQ unavailability returns a
structured error response instead of 500-ing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Path, Query

from admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "dlq"])


# ---------------------------------------------------------------------------
# GET /v1/admin/dlq
# ---------------------------------------------------------------------------


@router.get("/dlq", response_model=dict)
async def get_dlq(
    limit: int = Query(50, ge=1, le=500, description="Max entries to return"),
    user=Depends(require_admin),
) -> dict[str, Any]:
    """List entries in the ARQ Dead Letter Queue.

    Returns entries sorted by ``enqueued_at`` descending (most recent first).
    Each entry carries::

        {
            "uuid": "...",
            "job_name": "...",
            "payload": {...},
            "error": "...",
            "traceback": "...",
            "enqueued_at": "2026-06-15T12:00:00+00:00"
        }

    When Redis is unreachable the response carries ``status="redis_unavailable"``
    and an empty ``entries`` list.
    """
    from jobs.dlq import get_dlq_jobs

    queried_at = datetime.now(timezone.utc).isoformat()

    try:
        entries = await get_dlq_jobs(limit=limit)
        # Update gauge with current entry count
        try:
            from metrics import DLQ_SIZE
            DLQ_SIZE.set(len(entries))
        except Exception:
            pass
        return {
            "status": "ok",
            "queried_at": queried_at,
            "count": len(entries),
            "entries": entries,
        }
    except Exception as exc:
        logger.warning("GET /v1/admin/dlq failed: %s", exc)
        return {
            "status": "error",
            "queried_at": queried_at,
            "count": 0,
            "entries": [],
            "detail": str(exc),
        }


# ---------------------------------------------------------------------------
# POST /v1/admin/dlq/{uuid}/retry
# ---------------------------------------------------------------------------


@router.post("/dlq/{uuid}/retry", response_model=dict)
async def retry_dlq_entry(
    uuid: str = Path(..., description="UUID of the DLQ entry to retry"),
    user=Depends(require_admin),
) -> dict[str, Any]:
    """Re-enqueue a single DLQ entry back into the ARQ job queue.

    Returns ``{"status": "ok", "uuid": "..."}`` on success.
    Returns ``{"status": "not_found", "uuid": "..."}`` if the entry no longer
    exists (may have been purged or already retried).
    Returns ``{"status": "error", "detail": "..."}`` on Redis or ARQ failure.
    """
    from jobs.dlq import retry_dlq_job

    queried_at = datetime.now(timezone.utc).isoformat()

    try:
        ok = await retry_dlq_job(uuid)
        if ok:
            return {
                "status": "ok",
                "uuid": uuid,
                "queried_at": queried_at,
            }
        return {
            "status": "not_found",
            "uuid": uuid,
            "queried_at": queried_at,
            "detail": "DLQ entry not found — may have been purged or already retried",
        }
    except Exception as exc:
        logger.warning("POST /v1/admin/dlq/%s/retry failed: %s", uuid, exc)
        return {
            "status": "error",
            "uuid": uuid,
            "queried_at": queried_at,
            "detail": str(exc),
        }


# ---------------------------------------------------------------------------
# DELETE /v1/admin/dlq
# ---------------------------------------------------------------------------


@router.delete("/dlq", response_model=dict)
async def purge_dlq(
    user=Depends(require_admin),
) -> dict[str, Any]:
    """Delete **all** entries from the ARQ Dead Letter Queue.

    Returns ``{"status": "ok", "keys_deleted": N}`` on success.
    Returns ``{"status": "error", "detail": "..."}`` on failure.
    """
    from jobs.dlq import purge_dlq as _purge_dlq

    queried_at = datetime.now(timezone.utc).isoformat()

    try:
        deleted = await _purge_dlq()
        return {
            "status": "ok",
            "keys_deleted": deleted,
            "queried_at": queried_at,
        }
    except Exception as exc:
        logger.warning("DELETE /v1/admin/dlq failed: %s", exc)
        return {
            "status": "error",
            "queried_at": queried_at,
            "detail": str(exc),
        }
