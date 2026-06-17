"""B2GOPS-011 (#1281): In-app user alert routes.

Wave 1 of EPIC-B2GOPS (#1262) — Intelligent Alert System.

Endpoints (all authenticated):
  - GET    /v1/alerts/b2gops            — List alerts (paginated, filterable)
  - PATCH  /v1/alerts/b2gops/{id}/read  — Mark single alert as read
  - POST   /v1/alerts/b2gops/read-all   — Mark all alerts as read
  - DELETE /v1/alerts/b2gops/{id}       — Delete single alert
  - GET    /v1/alerts/b2gops/unread-count — Unread count badge
  - GET    /v1/alerts/b2gops/preferences  — Get alert preferences
  - PATCH  /v1/alerts/b2gops/preferences  — Update alert preferences
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_auth
from log_sanitizer import mask_user_id
from schemas.alerts_b2gops import (
    AlertPreferencesResponse,
    UnreadCountResponse,
    UpdateAlertPreferencesRequest,
    UserAlertListResponse,
    UserAlertResponse,
)
from schemas.common import SuccessMessageResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["alerts-b2gops"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_alert_response(row: dict) -> UserAlertResponse:
    """Convert a Supabase row dict into a UserAlertResponse."""
    return UserAlertResponse(
        id=row["id"],
        user_id=row["user_id"],
        type=row["type"],
        title=row["title"],
        body=row.get("body"),
        data=row.get("data") or {},
        is_read=row.get("is_read", False),
        read_at=row.get("read_at"),
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# GET /v1/alerts/b2gops — List alerts (paginated, filterable)
# ---------------------------------------------------------------------------


@router.get("/alerts/b2gops", response_model=UserAlertListResponse)
async def list_alerts(
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    alert_type: Optional[str] = Query(
        None, alias="type", description="Filter by event type"
    ),
    is_read: Optional[bool] = Query(
        None, description="Filter by read/unread status"
    ),
    user: dict = Depends(require_auth),
):
    """List user alerts with pagination and optional filters.

    Filters:
      - type: event type (new_matching_edital, deadline_approaching, etc.)
      - is_read: true/false to filter by read status
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
        if alert_type:
            query = query.eq("type", alert_type)
        if is_read is not None:
            query = query.eq("is_read", is_read)

        result = await sb_execute(
            query.order("created_at", desc=True).range(offset, offset + limit - 1)
        )

        alerts = [
            _row_to_alert_response(row)
            for row in (result.data or [])
        ]
        total = result.count if result.count is not None else len(alerts)

        return UserAlertListResponse(
            alerts=alerts,
            total=total,
            limit=limit,
            offset=offset,
        )

    except Exception as e:
        logger.error("Error listing alerts for user %s: %s", mask_user_id(user_id), e)
        raise HTTPException(status_code=500, detail="Erro ao listar alertas.")


# ---------------------------------------------------------------------------
# GET /v1/alerts/b2gops/unread-count — Badge count
# ---------------------------------------------------------------------------


@router.get("/alerts/b2gops/unread-count", response_model=UnreadCountResponse)
async def unread_count(
    user: dict = Depends(require_auth),
):
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
# PATCH /v1/alerts/b2gops/{id}/read — Mark single alert as read
# ---------------------------------------------------------------------------


@router.patch("/alerts/b2gops/{alert_id}/read", response_model=UserAlertResponse)
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
            raise HTTPException(status_code=404, detail="Alerta nao encontrado.")

        logger.info(
            "Alert %s marked as read for user %s",
            alert_id[:8], mask_user_id(user_id),
        )
        return _row_to_alert_response(result.data[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error marking alert %s as read for user %s: %s",
            alert_id[:8], mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao marcar alerta como lido.")


# ---------------------------------------------------------------------------
# POST /v1/alerts/b2gops/read-all — Mark all as read
# ---------------------------------------------------------------------------


@router.post("/alerts/b2gops/read-all", response_model=SuccessMessageResponse)
async def mark_all_read(
    user: dict = Depends(require_auth),
):
    """Mark all unread alerts as read for the current user."""
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        now = datetime.now(timezone.utc).isoformat()
        result = await sb_execute(
            sb.table("user_alerts")
            .update({"is_read": True, "read_at": now})
            .eq("user_id", user_id)
            .eq("is_read", False)
        )

        affected = len(result.data) if result.data else 0
        logger.info(
            "Marked %d alerts as read for user %s",
            affected, mask_user_id(user_id),
        )
        return {
            "success": True,
            "message": f"{affected} alerta(s) marcado(s) como lido(s).",
        }

    except Exception as e:
        logger.error(
            "Error marking all alerts as read for user %s: %s",
            mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao marcar alertas como lidos.")


# ---------------------------------------------------------------------------
# DELETE /v1/alerts/b2gops/{id} — Delete single alert
# ---------------------------------------------------------------------------


@router.delete("/alerts/b2gops/{alert_id}", response_model=SuccessMessageResponse)
async def delete_alert(
    alert_id: str,
    user: dict = Depends(require_auth),
):
    """Delete a single alert by ID."""
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("user_alerts")
            .delete()
            .eq("id", alert_id)
            .eq("user_id", user_id)
        )

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Alerta nao encontrado.")

        logger.info(
            "Alert %s deleted for user %s",
            alert_id[:8], mask_user_id(user_id),
        )
        return {"success": True, "message": "Alerta removido com sucesso."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error deleting alert %s for user %s: %s",
            alert_id[:8], mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao remover alerta.")


# ---------------------------------------------------------------------------
# GET /v1/alerts/b2gops/preferences — Get alert preferences
# ---------------------------------------------------------------------------


@router.get("/alerts/b2gops/preferences", response_model=AlertPreferencesResponse)
async def get_preferences(
    user: dict = Depends(require_auth),
):
    """Get the current user's alert notification preferences."""
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("user_alert_preferences")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
        )

        if not result.data:
            # Return defaults if no preferences set yet
            return AlertPreferencesResponse()

        row = result.data
        return AlertPreferencesResponse(
            channels=row.get("channels") or {"in_app": True},
            enabled_types=row.get("enabled_types") or [],
            quiet_hours=row.get("quiet_hours") or {"start": None, "end": None},
        )

    except Exception as e:
        logger.error(
            "Error fetching alert preferences for user %s: %s",
            mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao buscar preferencias.")


# ---------------------------------------------------------------------------
# PATCH /v1/alerts/b2gops/preferences — Update alert preferences
# ---------------------------------------------------------------------------


@router.patch("/alerts/b2gops/preferences", response_model=AlertPreferencesResponse)
async def update_preferences(
    body: UpdateAlertPreferencesRequest,
    user: dict = Depends(require_auth),
):
    """Update the current user's alert notification preferences.

    Uses upsert — creates preferences row if it doesn't exist,
    updates only the provided fields if it does.
    """
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        # Fetch existing preferences to merge
        existing = None
        try:
            existing_result = await sb_execute(
                sb.table("user_alert_preferences")
                .select("*")
                .eq("user_id", user_id)
                .maybe_single()
            )
            existing = existing_result.data
        except Exception:
            pass

        # Build merged preferences
        channels = (body.channels if body.channels is not None
                    else (existing.get("channels") if existing else {"in_app": True}))
        enabled_types = (body.enabled_types if body.enabled_types is not None
                         else (existing.get("enabled_types") if existing else []))
        quiet_hours = (body.quiet_hours if body.quiet_hours is not None
                       else (existing.get("quiet_hours") if existing else {"start": None, "end": None}))

        now = datetime.now(timezone.utc).isoformat()

        result = await sb_execute(
            sb.table("user_alert_preferences")
            .upsert({
                "user_id": user_id,
                "channels": channels,
                "enabled_types": enabled_types,
                "quiet_hours": quiet_hours,
                "updated_at": now,
            })
        )

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=500, detail="Erro ao atualizar preferencias.")

        logger.info(
            "Alert preferences updated for user %s",
            mask_user_id(user_id),
        )

        row = result.data[0]
        return AlertPreferencesResponse(
            channels=row.get("channels") or {"in_app": True},
            enabled_types=row.get("enabled_types") or [],
            quiet_hours=row.get("quiet_hours") or {"start": None, "end": None},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error updating alert preferences for user %s: %s",
            mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao atualizar preferencias.")
