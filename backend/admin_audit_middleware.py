"""#1974: Admin audit middleware — auto-log POST/PATCH/DELETE to admin_audit_log.

Intercepts requests to ``/v1/admin/*`` paths and registers a basic audit entry
in the ``admin_audit_log`` table. Routes that already call
``log_admin_action_db()`` explicitly with rich context set
``request.state.admin_audit_logged = True`` to prevent duplicate logging.

Graceful degradation: if the DB write fails, the error is logged at warning
level and the request proceeds uninterrupted.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


# Admin path prefix patterns — any path starting with one of these or
# containing a known admin segment triggers auto-logging.
_ADMIN_PATH_PATTERNS = (
    "/v1/admin/",
    "/v1/admin",
)

# Self-prefixed admin routers (registered at /v1/admin/, not under /v1/):
# admin_trace, admin_cron, admin_cnae_mapping, admin_llm_cost,
# admin_calibration, admin_billing_sync, admin_founding, admin_metrics,
# admin_dlq, admin_sessions, admin_log_level, admin_synthetic,
# admin_alerts, admin_data_retention, admin_circuit_breakers, admin_db_pool
_ADMIN_SELF_PREFIX = "/v1/admin/"


def _is_admin_path(path: str) -> bool:
    """Check if a request path targets an admin endpoint."""
    return path.startswith(_ADMIN_SELF_PREFIX)


def _infer_entity_type(path: str, action: str) -> str:
    """Infer entity_type from the URL path.

    Examples:
        /v1/admin/users/{id}        -> user
        /v1/admin/cache/{hash}      -> cache
        /v1/admin/feature-flags/... -> feature_flag
        /v1/admin/reconciliation/... -> reconciliation
        /v1/admin/filter-stats       -> filter_stats
        /v1/admin/cron-status        -> cron
        /v1/admin/support-sla        -> support_sla
        /v1/admin/trial-metrics      -> trial
        /v1/admin/at-risk-trials     -> trial
        /v1/admin/memory-snapshot    -> memory
        /v1/admin/users/segments     -> user
        /v1/admin/audit-log          -> audit_log
    """
    # Strip /v1/admin/ prefix and get the first meaningful segment
    rest = path.removeprefix(_ADMIN_SELF_PREFIX).strip("/")
    segments = rest.split("/") if rest else []

    if not segments:
        return "admin"

    # Entity type inference from first URL segment
    first = segments[0].lower()
    # Maps URL segment -> entity_type
    entity_map = {
        "users": "user",
        "cache": "cache",
        "feature-flags": "feature_flag",
        "reconciliation": "reconciliation",
        "filter-stats": "filter_stats",
        "cron-status": "cron",
        "support-sla": "support_sla",
        "trial-metrics": "trial",
        "at-risk-trials": "trial",
        "memory-snapshot": "memory",
        "audit-log": "audit_log",
        "subscriptions": "subscription",
        "circuit-breakers": "circuit_breaker",
        "data-retention": "data_retention",
        "db-pool": "db_pool",
        "log-level": "log_level",
        "synthetic": "synthetic",
        "test-alert": "alert",
        "digest-metrics": "digest",
        "billing-sync": "billing",
        "llm-cost": "llm_cost",
        "calibration": "calibration",
        "cnae-mapping": "cnae",
        "founding": "founding",
        "metrics": "metrics",
        "command": "command",
        "search-trace": "search_trace",
    }
    return entity_map.get(first, first)


def _infer_action(method: str, path: str) -> str:
    """Infer action name from HTTP method and URL path.

    Examples:
        POST /v1/admin/users          -> create_user
        DELETE /v1/admin/users/{id}   -> delete_user
        PATCH /v1/admin/feature-flags/{name} -> update_feature_flag
    """
    rest = path.removeprefix(_ADMIN_SELF_PREFIX).strip("/")
    segments = rest.split("/") if rest else []
    first = segments[0].lower() if segments else ""

    method_lower = method.lower()

    # Heuristic: POST/PATCH/DELETE + entity knowledge
    if method_lower == "post":
        return f"create_{first}" if first else "admin_action"
    elif method_lower == "patch":
        return f"update_{first}" if first else "admin_action"
    elif method_lower == "delete":
        return f"delete_{first}" if first else "admin_action"
    elif method_lower == "put":
        return f"update_{first}" if first else "admin_action"
    return f"{method_lower}_{first}" if first else "admin_action"


def _infer_entity_id(path: str, admin_id: str) -> str:
    """Infer entity_id from URL path. Falls back to admin_id if not found."""
    rest = path.removeprefix(_ADMIN_SELF_PREFIX).strip("/")
    segments = rest.split("/") if rest else []
    # entity ID is typically the second segment (e.g. /v1/admin/users/{id})
    if len(segments) >= 2:
        candidate = segments[1]
        # Skip known sub-resources (feature-flags is the entity, {name} is the ID)
        if segments[0].lower() == "feature-flags" and len(segments) >= 3:
            return segments[2]
        return candidate
    return admin_id


class AdminAuditMiddleware(BaseHTTPMiddleware):
    """#1974: Auto-log all POST/PATCH/DELETE requests to admin endpoints.

    Operates as a response-side middleware: captures the request BEFORE the
    handler runs and writes the audit entry AFTER the response is generated,
    so the entry includes only the context available from the request path.

    Routes that already call ``log_admin_action_db()`` with richer context
    should set ``request.state.admin_audit_logged = True`` to prevent the
    middleware from creating a duplicate entry.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        method = request.method

        # Only intercept mutating requests to admin paths
        if method not in ("POST", "PATCH", "PUT", "DELETE") or not _is_admin_path(path):
            return await call_next(request)

        # Extract admin_id from auth if available — will be None for unauthenticated requests
        admin_id = _extract_admin_id(request)
        if not admin_id:
            return await call_next(request)

        response = await call_next(request)

        # Skip if the route handler already logged (set by log_admin_action_db())
        if getattr(request.state, "admin_audit_logged", False):
            return response

        # Only log successful or client-error responses (2xx/4xx), not 5xx
        if response.status_code >= 500:
            return response

        action = _infer_action(method, path)
        entity_type = _infer_entity_type(path, action)
        entity_id = _infer_entity_id(path, admin_id)

        # Capture client IP
        ip_address = _extract_client_ip(request)

        # Fire-and-forget: log the audit entry in background
        try:
            from log_sanitizer import log_admin_action_db

            await log_admin_action_db(
                admin_id=admin_id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                details={
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                },
                ip_address=ip_address,
            )
        except Exception as e:
            logger.warning(
                "AdminAuditMiddleware: failed to log action %s %s: %s",
                method, path, e,
            )

        return response


def _extract_admin_id(request: Request) -> str | None:
    """Extract admin user ID from request.state.user (set by auth dependency).

    Returns None if the user is not authenticated or user data is not present.
    """
    user = getattr(request.state, "user", None)
    if user and isinstance(user, dict):
        return user.get("id")
    return None


def _extract_client_ip(request: Request) -> str | None:
    """Extract client IP from X-Forwarded-For or direct connection."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None
