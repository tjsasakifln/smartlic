"""#1974: Admin audit log query endpoint.

Provides a filtered, paginated query interface for the ``admin_audit_log`` table.
Only users with ``admin:super`` or ``admin:compliance`` role can access this
endpoint (enforced via ``require_admin_role``).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from rbac_granular import require_admin_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


# ============================================================================
# Pydantic models
# ============================================================================


class AuditLogEntry(BaseModel):
    """Single admin audit log entry."""

    id: str = Field(..., description="Audit log entry UUID")
    admin_id: str = Field(..., description="Admin user ID")
    action: str = Field(..., description="Action performed")
    entity_type: str = Field(..., description="Type of affected entity")
    entity_id: str = Field(..., description="ID of affected entity")
    details: dict = Field(default_factory=dict, description="Action details (PII sanitized)")
    ip: Optional[str] = Field(None, description="Client IP address")
    created_at: str = Field(..., description="ISO timestamp of the action")


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""

    entries: list[AuditLogEntry] = Field(..., description="List of audit log entries")
    total: int = Field(..., description="Total matching entries (before pagination)")
    limit: int = Field(..., description="Page size applied")
    offset: int = Field(..., description="Offset applied")


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/audit-log", response_model=AuditLogResponse)
async def get_audit_log(
    admin: dict = Depends(require_admin_role("admin:compliance")),
    admin_id: Optional[str] = Query(None, description="Filter by admin user ID"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (e.g. user, cache)"),
    action: Optional[str] = Query(None, description="Filter by action (e.g. assign_plan, create_user)"),
    from_date: Optional[str] = Query(None, alias="from", description="Start date (ISO 8601)"),
    to_date: Optional[str] = Query(None, alias="to", description="End date (ISO 8601)"),
    limit: int = Query(default=50, ge=1, le=200, description="Max results per page"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
) -> AuditLogResponse:
    """Query the admin audit log with optional filters.

    Requires ``admin:compliance`` or ``admin:super`` role.
    PII in the ``details`` field is sanitized at write time via
    ``log_sanitizer.sanitize_dict()``.

    **Filters:**
    - ``admin_id``: Filter by the admin who performed the action.
    - ``entity_type``: Filter by entity type (e.g. ``user``, ``cache``).
    - ``action``: Filter by action name (e.g. ``assign_plan``).
    - ``from`` / ``to``: ISO 8601 date range filter on ``created_at``.
    - ``limit``: Page size (1-200, default 50).
    - ``offset``: Pagination offset (default 0).
    """
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()

    # Build query
    query = sb.table("admin_audit_log").select("*", count="exact")

    if admin_id:
        query = query.eq("admin_id", admin_id)

    if entity_type:
        query = query.eq("entity_type", entity_type)

    if action:
        query = query.eq("action", action)

    if from_date:
        try:
            # Validate/parse ISO date
            datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            query = query.gte("created_at", from_date)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Formato de data 'from' invalido. Use ISO 8601.")

    if to_date:
        try:
            datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            query = query.lte("created_at", to_date)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Formato de data 'to' invalido. Use ISO 8601.")

    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)

    try:
        result = await sb_execute(query, category="read")
    except Exception as e:
        logger.error("Failed to query admin_audit_log: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar log de auditoria.")

    rows = result.data or []

    entries = [
        AuditLogEntry(
            id=row["id"],
            admin_id=row["admin_id"],
            action=row["action"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            details=row.get("details", {}),
            ip=row.get("ip"),
            created_at=row["created_at"],
        )
        for row in rows
    ]

    return AuditLogResponse(
        entries=entries,
        total=result.count or len(rows),
        limit=limit,
        offset=offset,
    )
