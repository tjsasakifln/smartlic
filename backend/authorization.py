"""Authorization helpers for SmartLic API.

Shared authorization logic used across multiple route modules.
Extracted from main.py as part of STORY-202 monolith decomposition.

STORY-291: Circuit breaker integration — when Supabase CB is open,
check_user_roles() returns (False, False) immediately without retrying.

#1778: Granular admin roles — replaces boolean is_admin with role-based
access control. See ``roles.py`` for role definitions and env-based resolution.
"""

import asyncio
import logging
import os

from fastapi import Depends, HTTPException
from log_sanitizer import mask_user_id
from roles import (
    AdminRole,
    get_user_roles_from_env,
    get_master_ids as _roles_get_master_ids,  # avoid shadowing
)
from schemas.common import validate_uuid

logger = logging.getLogger(__name__)


class ErrorCode:
    """Structured error codes for better frontend error handling"""
    DATE_RANGE_EXCEEDED = "DATE_RANGE_EXCEEDED"
    RATE_LIMIT = "RATE_LIMIT"
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    INVALID_SECTOR = "INVALID_SECTOR"
    INVALID_UF = "INVALID_UF"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"


def get_admin_ids() -> set[str]:
    """Get validated admin user IDs from environment variable (fallback/override).

    Each ID is validated as UUID v4; invalid entries are logged and skipped.
    """
    raw = os.getenv("ADMIN_USER_IDS", "")
    valid_ids: set[str] = set()
    for uid in raw.split(","):
        uid = uid.strip()
        if not uid:
            continue
        try:
            valid_ids.add(validate_uuid(uid, "admin_id"))
        except ValueError as e:
            logger.warning(f"Invalid admin ID in ADMIN_USER_IDS skipped: {e}")
    return valid_ids


async def check_user_roles(user_id: str) -> tuple[bool, bool]:
    """
    Check user's admin and master status from Supabase.

    STORY-291: When Supabase circuit breaker is open, returns (False, False)
    immediately without retrying — user treated as regular.

    Returns:
        tuple: (is_admin, is_master)
        - is_admin: Can manage users via /admin/* endpoints
        - is_master: Has full feature access (Excel, unlimited quota)

    Hierarchy: admin > master > regular users
    Admins automatically get master privileges.
    """
    for attempt in range(2):
        try:
            from supabase_client import get_supabase, sb_execute, CircuitBreakerOpenError
            sb = get_supabase()

            # Get profile - try with is_admin first, fallback to just plan_type
            try:
                profile = await sb_execute(
                    sb.table("profiles")
                    .select("is_admin, plan_type")
                    .eq("id", user_id)
                    .single()
                )
            except CircuitBreakerOpenError:
                raise  # Don't retry CB open — fast fail
            except Exception:
                # is_admin column might not exist yet - fallback
                profile = await sb_execute(
                    sb.table("profiles")
                    .select("plan_type")
                    .eq("id", user_id)
                    .single()
                )

            if not profile.data:
                return (False, False)

            is_admin = profile.data.get("is_admin", False)
            plan_type = profile.data.get("plan_type", "")

            # Admin implies master access
            is_master = is_admin or plan_type == "master"

            if is_admin:
                logger.debug(f"User {mask_user_id(user_id)} is ADMIN (profiles.is_admin)")
            elif is_master:
                logger.debug(f"User {mask_user_id(user_id)} is MASTER (profiles.plan_type)")

            return (is_admin, is_master)

        except CircuitBreakerOpenError:
            # STORY-291: CB open — skip retries, return non-admin immediately
            logger.warning(
                f"ROLE CHECK SKIPPED for user {mask_user_id(user_id)}: "
                f"Supabase circuit breaker is OPEN. User treated as regular."
            )
            return (False, False)
        except Exception as e:
            if attempt == 0:
                logger.debug(f"Retry user roles check for {mask_user_id(user_id)} after error: {type(e).__name__}")
                await asyncio.sleep(0.3)
                continue
            logger.warning(
                f"ROLE CHECK FAILED for user {mask_user_id(user_id)} after 2 attempts: {type(e).__name__}. "
                f"User will be treated as regular (non-admin/non-master)."
            )
            return (False, False)
    return (False, False)


async def is_admin(user_id: str) -> bool:
    """
    Check if user can access /admin/* endpoints.

    Sources (in order):
    1. ADMIN_USER_IDS env var (fallback/override)
    2. Supabase profiles.is_admin = true
    """
    # Fast path: check env var first (no DB call)
    admin_ids = get_admin_ids()
    if user_id.lower() in admin_ids:
        return True

    # Check Supabase
    is_admin_flag, _ = await check_user_roles(user_id)
    return is_admin_flag


async def has_master_access(user_id: str) -> bool:
    """
    Check if user has full feature access (master or admin).

    Sources:
    1. ADMIN_USER_IDS env var (admins get master access)
    2. Supabase profiles.is_admin = true (admins get master access)
    3. Supabase profiles.plan_type = 'master'
    """
    # Fast path: check env var first (no DB call)
    admin_ids = get_admin_ids()
    if user_id.lower() in admin_ids:
        return True

    # Check Supabase
    is_admin_flag, is_master = await check_user_roles(user_id)
    return is_admin_flag or is_master


def get_master_quota_info(is_admin: bool = False):
    """
    Get quota info for admin/master users - returns sala_guerra (highest tier).

    Admins/masters bypass all quota restrictions and have full access to all features.
    """
    from quota import QuotaInfo, PLAN_CAPABILITIES
    from datetime import datetime, timezone

    plan_name = "SmartLic Pro (Admin)" if is_admin else "SmartLic Pro (Master)"

    return QuotaInfo(
        allowed=True,
        plan_id="sala_guerra",
        plan_name=plan_name,
        capabilities=PLAN_CAPABILITIES["sala_guerra"],
        quota_used=0,
        quota_remaining=999999,  # Unlimited for admins/masters
        quota_reset_date=datetime.now(timezone.utc),
        trial_expires_at=None,
        error_message=None,
    )


# ===========================================================================
# #1778: Granular Admin Roles — role-based access control
# ===========================================================================


def get_master_ids() -> set[str]:
    """Get validated master user IDs from MASTER_USER_IDS env var.
    Delegates to roles.get_master_ids().
    """
    return _roles_get_master_ids()


async def get_user_roles(user_id: str) -> set[str]:
    """Get all admin roles for a user.

    Resolution order:
    1. MASTER_USER_IDS env var -> all roles (highest priority)
    2. ADMIN_ROLES env var -> explicit role mapping
    3. ADMIN_USER_IDS env var (legacy) -> DASHBOARD only (minimum privilege)
    4. admin_roles table in Supabase -> stored roles (DB fallback)

    Returns:
        set[str]: Set of role strings (e.g. {"dashboard", "user_manager"}).
                  Empty set for regular (non-admin) users.

    The env var resolution is fast (no DB call) and serves as the primary
    source for hardcoded admins. The DB table is checked as fallback for
    admins configured at runtime via the admin dashboard.
    """
    # Fast path: check env vars first (no DB call)
    roles = get_user_roles_from_env(user_id)
    if roles is not None:
        return roles

    # Fallback: check admin_roles table in Supabase
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        result = await sb_execute(
            sb.table("admin_roles")
            .select("roles")
            .eq("user_id", user_id)
            .single(),
            category="read",
        )
        if result.data and result.data.get("roles"):
            return set(result.data["roles"])
    except Exception:
        # Table may not exist yet, or other transient error
        # Silently fall through — user has no roles
        pass

    return set()


def require_role(*roles: str):
    """FastAPI dependency factory: require specific admin role(s).

    Usage::

        @router.get("/admin/users")
        async def list_users(user=Depends(require_role("data_access", "master"))):
            ...

    The dependency checks that the authenticated user has at least one of
    the specified roles. If not, raises HTTP 403.

    Args:
        *roles: One or more required role strings (e.g. "data_access", "master").
    """
    from auth import require_auth as _require_auth

    async def _checker(user: dict = Depends(_require_auth)) -> dict:
        user_roles = await get_user_roles(user["id"])
        if not any(r in user_roles for r in roles):
            raise HTTPException(
                status_code=403,
                detail="Permissao insuficiente para esta operacao",
            )
        return user
    return _checker


# Shorthand dependencies for common role combinations.
# Each requires either the specific role OR master (super admin).

require_data_access = require_role(
    AdminRole.DATA_ACCESS.value,
    AdminRole.MASTER.value,
)

require_user_manager = require_role(
    AdminRole.USER_MANAGER.value,
    AdminRole.MASTER.value,
)

require_billing = require_role(
    AdminRole.BILLING.value,
    AdminRole.MASTER.value,
)

require_dashboard = require_role(
    AdminRole.DASHBOARD.value,
    AdminRole.MASTER.value,
)


# ===========================================================================
# Backward-compatible aliases (STORY-226 AC8)
# These allow existing code that imports the underscore-prefixed names to
# continue working without modification.  New code should use the public names.
# ===========================================================================
_get_admin_ids = get_admin_ids
_check_user_roles = check_user_roles
_is_admin = is_admin
_has_master_access = has_master_access
_get_master_quota_info = get_master_quota_info
