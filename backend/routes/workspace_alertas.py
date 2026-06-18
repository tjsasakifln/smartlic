"""B2GOPS-011 (#2021): Workspace alertas endpoints.

Reads from the existing user_alerts table (Wave 1 of EPIC-B2GOPS)
and exposes them under the /v1/workspace/alertas prefix.

Endpoints:
  - GET    /v1/workspace/alertas               — List alerts (paginated, filterable)
  - PATCH  /v1/workspace/alertas/{id}/read     — Mark alert as read
  - GET    /v1/workspace/alertas/unread-count  — Unread count for badge
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_auth
from log_sanitizer import mask_user_id
from schemas.alerts_b2gops import UnreadCountResponse
from schemas.workspace_alertas import AlertaItem, AlertaResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspace"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_alerta(row: dict) -> AlertaItem:
    """Convert a user_alerts row dict into an AlertaItem."""
    return AlertaItem(
        id=row["id"],
        user_id=row["user_id"],
        tipo=row["type"],
        titulo=row["title"],
        descricao=row.get("body"),
        metadata=row.get("data") or {},
        lido=row.get("is_read", False),
        read_at=row.get("read_at"),
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# GET /v1/workspace/alertas — List alerts (paginated, filterable)
# ---------------------------------------------------------------------------


@router.get("/workspace/alertas", response_model=AlertaResponse)
async def list_alertas(
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    tipo: Optional[str] = Query(
        None, alias="type", description="Filter by event type"
    ),
    data_inicio: Optional[str] = Query(
        None, description="Start date filter (ISO 8601)"
    ),
    data_fim: Optional[str] = Query(
        None, description="End date filter (ISO 8601)"
    ),
    lido: Optional[bool] = Query(
        None, alias="status", description="Filter by read status (true=read, false=unread)"
    ),
    user: dict = Depends(require_auth),
):
    """List workspace alerts with pagination and optional filters.

    Filters:
      - tipo: event type (new_matching_edital, deadline_approaching, etc.)
      - data_inicio / data_fim: date range filter
      - lido: true/false to filter by read status
    """
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        query = (
            sb.table("user_alerts")
            .select("*", count="exact")
            .eq("user_id", user_id)
        )

        # Apply optional filters
        if tipo:
            query = query.eq("type", tipo)
        if lido is not None:
            query = query.eq("is_read", lido)
        if data_inicio:
            query = query.gte("created_at", data_inicio)
        if data_fim:
            query = query.lte("created_at", data_fim)

        result = await sb_execute(
            query.order("created_at", desc=True).range(offset, offset + limit - 1)
        )

        alertas = [
            _row_to_alerta(row)
            for row in (result.data or [])
        ]
        total = result.count if result.count is not None else len(alertas)

        return AlertaResponse(
            alertas=alertas,
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error(
            "Error listing workspace alertas for user %s: %s",
            mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao listar alertas.")


# ---------------------------------------------------------------------------
# GET /v1/workspace/alertas/unread-count — Badge count
# ---------------------------------------------------------------------------


@router.get(
    "/workspace/alertas/unread-count",
    response_model=UnreadCountResponse,
)
async def unread_count(user: dict = Depends(require_auth)):
    """Get the count of unread alerts for the badge in the UI."""
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("user_alerts")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_read", False)
        )

        count = result.count if result.count is not None else 0
        return UnreadCountResponse(unread_count=count)

    except Exception as e:
        logger.error(
            "Error counting unread alerts for user %s: %s",
            mask_user_id(user_id), e,
        )
        return UnreadCountResponse(unread_count=0)


# ---------------------------------------------------------------------------
# PATCH /v1/workspace/alertas/{id}/read — Mark alert as read
# ---------------------------------------------------------------------------


@router.patch(
    "/workspace/alertas/{alert_id}/read",
    response_model=AlertaItem,
)
async def mark_read(
    alert_id: str,
    user: dict = Depends(require_auth),
):
    """Mark a single alert as read."""
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("user_alerts")
            .update({
                "is_read": True,
                "read_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", alert_id)
            .eq("user_id", user_id)
        )

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Alerta não encontrado.")

        logger.info(
            "Alert %s marked as read for user %s",
            alert_id[:8], mask_user_id(user_id),
        )
        return _row_to_alerta(result.data[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error marking alert %s as read for user %s: %s",
            alert_id[:8], mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao marcar alerta como lido.")
