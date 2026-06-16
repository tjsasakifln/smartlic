"""#1877 AC2: Data retention admin status endpoint.

Provides a read-only admin endpoint to inspect the last purge run per table:

    GET /v1/admin/data-retention/status

Returns per-table purge stats including timestamps, row counts, and any
errors from the most recent purge cycle.

Data is read from Redis keys written by ``run_data_retention_purge()``.
Falls back gracefully when Redis is unavailable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends

from admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "data_retention"])

_REDIS_TTL = 7 * 86400  # 7 days — must match data_retention.py


@router.get("/data-retention/status", response_model=dict)
async def get_data_retention_status(
    user=Depends(require_admin),
) -> dict[str, Any]:
    """Return the last purge status per table.

    Reads data from Redis keys set by the data retention purge cycle.
    Falls back gracefully when Redis is unavailable.

    Returns::

        {
            "status": "ok",
            "queried_at": "2026-06-16T12:00:00+00:00",
            "tables": [
                {
                    "name": "trial_email_log",
                    "last_purge_at": "2026-06-16T12:00:00+00:00",
                    "rows_purged_last": 42,
                    "status": "success"
                },
                ...
            ],
            "total_rows_purged_last": 123,
            "last_cycle_duration_seconds": 5.23
        }
    """
    queried_at = datetime.now(timezone.utc).isoformat()

    try:
        from redis_pool import get_redis_pool
        redis = await get_redis_pool()

        tables: list[dict[str, Any]] = []
        total_rows = 0
        status = "ok"

        for tbl_name in ("trial_email_log", "messages", "ingestion_checkpoints"):
            table_info: dict[str, Any] = {
                "name": tbl_name,
                "last_purge_at": None,
                "rows_purged_last": 0,
                "status": "unknown",
            }

            try:
                last_run_raw = await redis.get(f"data_retention:last_run:{tbl_name}")
                if last_run_raw:
                    table_info["last_purge_at"] = last_run_raw.decode()

                rows_raw = await redis.get(f"data_retention:last_rows:{tbl_name}")
                if rows_raw:
                    table_info["rows_purged_last"] = int(rows_raw.decode())

                error_raw = await redis.get(f"data_retention:last_error:{tbl_name}")
                if error_raw:
                    table_info["status"] = "error"
                    table_info["error"] = error_raw.decode()
                else:
                    table_info["status"] = "success"
            except Exception:
                table_info["status"] = "redis_unavailable"

            total_rows += table_info["rows_purged_last"]
            tables.append(table_info)

        # Read overall cycle duration
        duration = 0.0
        try:
            duration_raw = await redis.get("data_retention:last_duration")
            if duration_raw:
                duration = float(duration_raw.decode())
        except Exception:
            pass

        return {
            "status": status,
            "queried_at": queried_at,
            "tables": tables,
            "total_rows_purged_last": total_rows,
            "last_cycle_duration_seconds": round(duration, 2),
        }
    except Exception as exc:
        logger.warning("GET /v1/admin/data-retention/status failed: %s", exc)
        return {
            "status": "error",
            "queried_at": queried_at,
            "tables": [],
            "total_rows_purged_last": 0,
            "last_cycle_duration_seconds": 0,
            "detail": str(exc),
        }
