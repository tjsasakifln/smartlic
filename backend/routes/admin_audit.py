"""Admin audit log query endpoint.

ADMIN-AUDIT (#1974): ``GET /v1/admin/audit-log`` — query the immutable
admin audit trail. Requires ``admin:compliance`` role (or ``admin:super``).

Filtering parameters:
- ``admin_id`` — filter by admin UUID
- ``entity_type`` — filter by entity type (e.g. ``"user"``, ``"cache"``)
- ``action`` — filter by action name (e.g. ``"user.assign-plan"``)
- ``from`` — ISO 8601 start date (inclusive)
- ``to`` — ISO 8601 end date (inclusive)
- ``limit`` — page size (default 100, max 500)
- ``offset`` — page offset (default 0)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from rbac_granular import require_admin_compliance
from schemas.admin import AdminAuditLogResponse, AdminAuditLogEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "audit"])


@router.get(
    "/audit-log",
    response_model=AdminAuditLogResponse,
    summary="Query admin audit log (immutable trail)",
)
async def get_admin_audit_log(
    admin_id: Optional[str] = Query(None, description="Filter by admin UUID"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (e.g. 'user', 'cache')"),
    action: Optional[str] = Query(None, description="Filter by action name (e.g. 'user.assign-plan')"),
    date_from: Optional[str] = Query(None, alias="from", description="Start date (ISO 8601, inclusive)"),
    date_to: Optional[str] = Query(None, alias="to", description="End date (ISO 8601, inclusive)"),
    limit: int = Query(100, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Page offset"),
    admin: dict = Depends(require_admin_compliance),
    request: Request = None,
):
    """Query the immutable admin audit trail.

    Returns admin actions sorted by ``created_at`` descending (most recent
    first). At least one filter is strongly recommended for performance
    on large datasets; without filters the query covers the full table.
    """
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    table = sb.table("admin_audit_log")

    # Build query filters
    query = table.select("*", count="exact")
    query_count = table.select("id", count="exact")

    if admin_id:
        query = query.eq("admin_id", admin_id)
        query_count = query_count.eq("admin_id", admin_id)
    if entity_type:
        query = query.eq("entity_type", entity_type)
        query_count = query_count.eq("entity_type", entity_type)
    if action:
        query = query.eq("action", action)
        query_count = query_count.eq("action", action)
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            if dt_from.tzinfo is None:
                dt_from = dt_from.replace(tzinfo=timezone.utc)
            query = query.gte("created_at", dt_from.isoformat())
            query_count = query_count.gte("created_at", dt_from.isoformat())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid 'from' date format: {date_from}")
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to)
            if dt_to.tzinfo is None:
                dt_to = dt_to.replace(tzinfo=timezone.utc)
            query = query.lte("created_at", dt_to.isoformat())
            query_count = query_count.lte("created_at", dt_to.isoformat())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid 'to' date format: {date_to}")

    # Order by created_at descending, apply pagination
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)

    try:
        count_result = await sb_execute(query_count, category="read")
        total = count_result.count if count_result.count is not None else 0

        result = await sb_execute(query, category="read")
        rows = result.data if result.data else []
    except Exception as e:
        logger.error("ADMIN-AUDIT (#1974): failed to query audit log: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao consultar log de auditoria")

    entries = []
    for row in rows:
        entries.append(
            AdminAuditLogEntry(
                id=row["id"],
                admin_id=row["admin_id"],
                action=row["action"],
                entity_type=row["entity_type"],
                entity_id=row.get("entity_id"),
                details=row.get("details", {}),
                ip=row.get("ip"),
                created_at=row["created_at"],
            )
        )

    return AdminAuditLogResponse(
        entries=entries,
        total=total,
        limit=limit,
        offset=offset,
    )
