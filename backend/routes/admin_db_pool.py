"""Issue #1916: Admin endpoint for DB pool monitoring dashboard.

Provides a read-only snapshot of the current Supabase PostgreSQL connection
pool state, sampled every call. Designed for the system admin dashboard
at ``/v1/admin/db-pool``.

Admin-only (requires admin or master role).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "db-pool"])


@router.get("/db-pool")
async def get_db_pool_status(
    admin: dict = Depends(require_admin),
) -> dict:
    """Return current Supabase connection pool snapshot.

    Queries ``pg_stat_activity`` via the ``get_db_pool_stats`` RPC function
    (or falls back to in-process tracked counters). Includes:

        - ``active``, ``idle``, ``idle_in_transaction``, ``total``, ``max``,
          ``waiting`` connection counts
        - ``utilization`` ratio (0-1)
        - ``source`` indicator (``pg_stat_activity`` | ``tracked`` | ``error``)
        - ``threshold`` — the configured alert threshold (80% warning, 85% alert)
        - ``status`` — ``"healthy"`` / ``"degraded"`` / ``"critical"``

    **Requires:** admin or master role.
    **Target:** <200ms (single RPC call).
    """
    try:
        from monitoring.db_pool_monitor import get_db_pool_stats

        stats = await get_db_pool_stats()

        utilization = stats.get("utilization", 0.0)
        if utilization > 0.85:
            status = "critical"
        elif utilization > 0.80:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "active": stats.get("active", 0),
            "idle": stats.get("idle", 0),
            "idle_in_transaction": stats.get("idle_in_transaction", 0),
            "total": stats.get("total", 0),
            "max": stats.get("max", 0),
            "waiting": stats.get("waiting", 0),
            "utilization": utilization,
            "utilization_pct": round(utilization * 100, 1),
            "source": stats.get("source", "unknown"),
            "threshold_warning_pct": 80,
            "threshold_critical_pct": 85,
        }
    except Exception as e:
        logger.error("Issue #1916: GET /v1/admin/db-pool failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Nao foi possivel obter estatisticas do pool de conexoes",
        )
