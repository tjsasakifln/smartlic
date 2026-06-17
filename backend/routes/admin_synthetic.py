"""Issue #1869 — Synthetic monitoring admin endpoint.

GET /v1/admin/synthetic/last-run — Returns the last synthetic monitor
result and consecutive failure count from Redis.  Admin-only.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from admin import require_admin_ops
from schemas.admin import AdminSyntheticResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/synthetic/last-run", response_model=AdminSyntheticResponse)
async def get_synthetic_last_run(
    user=Depends(require_admin_ops),
) -> AdminSyntheticResponse:
    """Return the last synthetic monitor run result and consecutive failure count.

    Data is fetched from Redis (stored by the ARQ cron job in
    ``backend/jobs/cron/synthetic_monitor.py``).  If Redis is unavailable
    or no runs have completed, returns a "no_data" status.
    """
    try:
        from jobs.cron.synthetic_monitor import _get_state

        last_result = await _get_state("last_result")
        consecutive_failures = await _get_state("consecutive_failures") or 0

        if last_result is None:
            return AdminSyntheticResponse(
                status="no_data",
                consecutive_failures=consecutive_failures,
            )

        return AdminSyntheticResponse(
            status=last_result.get("status", "unknown"),
            queried_at=last_result.get("queried_at"),
            overall_elapsed_ms=last_result.get("overall_elapsed_ms"),
            stages=last_result.get("stages", {}),
            timings=last_result.get("timings", {}),
            consecutive_failures=consecutive_failures,
        )
    except Exception as exc:
        logger.warning("synthetic/last-run failed: %s", exc)
        return AdminSyntheticResponse(status="error", detail=str(exc))
