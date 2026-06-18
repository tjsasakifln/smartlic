"""Admin audit logging — INSERT-only immutable trail for admin actions.

ADMIN-AUDIT (#1974): Logs every admin mutation to the ``admin_audit_log``
Supabase table for LGPD compliance (Art. 37 — accountability).

The module provides:

1. ``log_admin_action()`` — async helper that inserts a row into
   ``admin_audit_log`` via the service_role Supabase client (bypasses RLS).

2. ``get_client_ip()`` — extracts the real client IP from a FastAPI
   ``Request``, respecting X-Forwarded-For and X-Real-IP headers.

3. ``AuditLogger`` — FastAPI dependency class for injection into admin
   endpoints via ``Depends(get_audit_logger)``.

Usage from an admin endpoint::

    from admin_audit import log_admin_action, get_client_ip

    @router.post("/users/{user_id}/assign-plan")
    async def assign_plan(
        user_id: str = Path(...),
        plan_id: str = Query(...),
        admin: dict = Depends(require_admin_users),
        request: Request = None,
    ):
        # ... perform action ...
        await log_admin_action(
            admin_id=admin["id"],
            action="user.assign-plan",
            entity_type="user",
            entity_id=user_id,
            details={"plan_id": plan_id},
            request=request,
        )
        return {"assigned": True, "user_id": user_id, "plan_id": plan_id}

The sanitizer from ``log_sanitizer`` is applied to ``details`` before
persisting to the database to prevent PII leakage in the audit trail.
"""

import logging
from typing import Any, Optional

from fastapi import Request
from log_sanitizer import sanitize_dict

logger = logging.getLogger(__name__)


def get_client_ip(request: Optional[Request]) -> Optional[str]:
    """Extract the real client IP from a FastAPI Request.

    Respects (in order of precedence):
    1. ``X-Forwarded-For`` header (first IP in comma-separated list)
    2. ``X-Real-IP`` header
    3. ``request.client.host`` (direct connection)

    Returns ``None`` if no request is provided or no IP can be determined.
    """
    if request is None:
        return None

    # 1. X-Forwarded-For — trust the first IP (closest to client)
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        first_ip = xff.split(",")[0].strip()
        if first_ip:
            return first_ip

    # 2. X-Real-IP
    xri = request.headers.get("X-Real-IP")
    if xri:
        return xri.strip()

    # 3. Direct connection
    if request.client and request.client.host:
        return request.client.host

    return None


async def log_admin_action(
    admin_id: str,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    request: Optional[Request] = None,
) -> None:
    """Log an admin action to the immutable ``admin_audit_log`` table.

    This is the primary entry point for audit logging from admin endpoints.
    It sanitizes ``details`` via ``log_sanitizer.sanitize_dict`` before
    persisting to ensure no PII leaks into the audit trail.

    Args:
        admin_id: UUID of the admin performing the action.
        action: Machine-readable action name (e.g. ``"user.assign-plan"``,
            ``"user.delete"``, ``"cache.clear"``).
        entity_type: Type of entity affected (e.g. ``"user"``, ``"cache"``,
            ``"feature_flag"``).
        entity_id: Optional ID of the affected entity.
        details: Optional structured metadata about the action. Will be
            sanitized via ``sanitize_dict`` before storage.
        request: Optional FastAPI ``Request`` — used to extract the client IP
            via ``get_client_ip()``. Pass ``None`` for background/cron tasks.

    Raises:
        Exception: Failures are logged and swallowed — audit logging is
            best-effort and MUST NOT break the calling endpoint.
    """
    ip = get_client_ip(request)
    sanitized_details = sanitize_dict(details) if details else {}

    row = {
        "admin_id": admin_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "details": sanitized_details,
        "ip": ip,
    }

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        await sb_execute(
            sb.table("admin_audit_log").insert(row),
            category="write",
        )
        logger.info(
            "ADMIN-AUDIT %s admin=%s entity_type=%s entity_id=%s",
            action,
            admin_id,
            entity_type,
            entity_id or "-",
        )
    except Exception as exc:
        # Audit logging is best-effort — never let it break the caller.
        logger.warning(
            "ADMIN-AUDIT (#1974): failed to persist audit entry "
            "action=%s admin=%s: %s",
            action,
            admin_id,
            exc,
        )


class AuditLogger:
    """FastAPI-injectable audit logger for admin endpoints.

    Usage in route definitions::

        from admin_audit import AuditLogger, get_audit_logger

        @router.post("/some-action")
        async def some_action(
            ...,
            audit: AuditLogger = Depends(get_audit_logger),
        ):
            # ... perform action ...
            await audit.log("my.action", entity_type="widget", entity_id="...")

    This is a convenience wrapper for ``log_admin_action`` that captures
    the ``request`` once at dependency resolution time so individual
    endpoint handlers don't need to pass it.
    """

    def __init__(self, request: Optional[Request] = None) -> None:
        self._request = request

    async def log(
        self,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
        admin_id: Optional[str] = None,
    ) -> None:
        """Log an admin audit event.

        Args:
            action: Machine-readable action name.
            entity_type: Type of entity affected.
            entity_id: Optional ID of the affected entity.
            details: Optional structured metadata (auto-sanitized).
            admin_id: Admin UUID. If not provided, the endpoint is responsible
                for passing it — but typically this is obtained from the auth
                dependency and passed explicitly.
        """
        if admin_id is None:
            logger.warning(
                "ADMIN-AUDIT (#1974): log() called without admin_id — "
                "action=%s entity_type=%s",
                action,
                entity_type,
            )
            return

        await log_admin_action(
            admin_id=admin_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            request=self._request,
        )


async def get_audit_logger(request: Request = None) -> AuditLogger:
    """FastAPI dependency that provides an ``AuditLogger`` instance.

    Usage::

        audit: AuditLogger = Depends(get_audit_logger)
    """
    return AuditLogger(request=request)
