"""Append-only audit logger for organization-level mutations (RBAC-ORG-001 AC8).

Single entry point — `log_org_event(...)` — used by route handlers
whenever they perform a privileged action. Failures are swallowed and
logged at WARNING level: the audit log is best-effort, never blocking.

Keep this module dependency-light (no app-state imports) so it can be
called from any handler without circular imports.
"""

from __future__ import annotations

import logging
from typing import Optional

from log_sanitizer import mask_user_id

logger = logging.getLogger(__name__)


# Allowed action discriminators — must match the CHECK constraint in
# `supabase/migrations/20260428100300_organization_audit_log.sql`.
AuditAction = str

VALID_ACTIONS: frozenset[str] = frozenset({
    "invite_sent",
    "invite_accepted",
    "member_removed",
    "member_left",
    "role_changed",
    "transfer_ownership",
    "org_updated",
    "org_deleted",
    "logo_updated",
})


async def log_org_event(
    *,
    org_id: str,
    actor_user_id: str,
    action: AuditAction,
    target_user_id: Optional[str] = None,
    old_value: Optional[str] = None,
    new_value: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Insert an audit row. Never raises — best-effort.

    Args:
        org_id: organization UUID
        actor_user_id: who performed the action (current authenticated user)
        action: one of VALID_ACTIONS
        target_user_id: who the action was performed on (if applicable)
        old_value: previous value (e.g. role before change)
        new_value: new value (e.g. role after change)
        metadata: free-form JSONB extra context
    """
    if action not in VALID_ACTIONS:
        # Programmer error — log loudly but don't crash the request.
        logger.error(
            "audit: rejected unknown action=%r org_id=%s actor=%s",
            action,
            org_id,
            mask_user_id(actor_user_id),
        )
        return

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        payload = {
            "org_id": org_id,
            "actor_user_id": actor_user_id,
            "action": action,
            "target_user_id": target_user_id,
            "old_value": old_value,
            "new_value": new_value,
            "metadata": metadata or {},
        }
        await sb_execute(
            sb.table("organization_audit_log").insert(payload),
            category="write",
        )
    except Exception as e:
        # Never let audit failure break the user-facing operation.
        logger.warning(
            "audit: log_org_event failed action=%s org_id=%s err=%s",
            action,
            org_id,
            type(e).__name__,
        )


async def fetch_audit_log(
    *,
    org_id: str,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict], int]:
    """Return (rows, total_count) for paginated audit-log reads (AC9)."""
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()

    # 1) Page of rows
    page_query = (
        sb.table("organization_audit_log")
        .select("*")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .range(offset, offset + max(0, limit - 1))
    )
    page_result = await sb_execute(page_query, category="read")

    # 2) Total count (separate exact-count query — Supabase doesn't return
    #    a count by default).
    count_query = (
        sb.table("organization_audit_log")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .limit(1)
    )
    count_result = await sb_execute(count_query, category="read")
    total = getattr(count_result, "count", None) or 0

    return (page_result.data or []), total
