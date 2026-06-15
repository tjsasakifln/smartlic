"""Admin role definitions and role resolution from environment variables.

Provides granular admin roles to replace the boolean is_admin model,
supporting least-privilege principle and LGPD compliance.

Roles (least to most privileged):
    DASHBOARD    - View dashboards and metrics (no PII)
    USER_MANAGER - Manage users (CRUD operations)
    BILLING      - Access billing/reconciliation data
    DATA_ACCESS  - Access PII (LGPD-sensitive data)
    MASTER       - Super admin (all roles)

Resolution order:
    1. MASTER_USER_IDS env var -> all roles (highest priority)
    2. ADMIN_ROLES env var -> explicit role mapping per user
    3. ADMIN_USER_IDS env var (legacy) -> DASHBOARD only (minimum privilege)
    4. admin_roles table in Supabase -> stored roles (checked by caller)
"""

import logging
import os
from enum import Enum

from schemas.common import validate_uuid

logger = logging.getLogger(__name__)


class AdminRole(str, Enum):
    """Granular admin roles for least-privilege access control.

    Each role represents a specific permission scope:
    - DASHBOARD: View metrics and dashboards (no PII exposure)
    - USER_MANAGER: Create, update, delete users
    - BILLING: Access billing/reconciliation data
    - DATA_ACCESS: Access PII and LGPD-sensitive data
    - MASTER: Super admin with all permissions
    """
    DASHBOARD = "dashboard"
    USER_MANAGER = "user_manager"
    BILLING = "billing"
    DATA_ACCESS = "data_access"
    MASTER = "master"


# All role values — used for MASTER-level access and validation
_ALL_ROLES: set[str] = {role.value for role in AdminRole}


def get_master_ids() -> set[str]:
    """Get validated master user IDs from MASTER_USER_IDS env var.

    Masters inherit all admin roles automatically.
    Each ID is validated as UUID v4; invalid entries are logged and skipped.
    """
    raw = os.getenv("MASTER_USER_IDS", "")
    valid_ids: set[str] = set()
    for uid in raw.split(","):
        uid = uid.strip()
        if not uid:
            continue
        try:
            valid_ids.add(validate_uuid(uid, "master_id"))
        except ValueError as e:
            logger.warning(f"Invalid master ID in MASTER_USER_IDS skipped: {e}")
    return valid_ids


def parse_admin_roles() -> dict[str, set[str]]:
    """Parse ADMIN_ROLES env var into user_id -> roles mapping.

    Format:
        user_id:role1,role2;user_id:role1,role2,role3

    Example:
        550e8400-e29b-41d4-a716-446655440000:dashboard,user_manager
        ;550e8400-e29b-41d4-a716-446655440001:data_access,billing

    Rules:
    - Entries are separated by semicolons
    - User ID and roles are separated by colon
    - Roles are comma-separated
    - Invalid user IDs are logged and skipped (fail-safe)
    - Unknown role names are logged and skipped
    - Empty entries are silently ignored
    """
    raw = os.getenv("ADMIN_ROLES", "")
    if not raw or not raw.strip():
        return {}

    result: dict[str, set[str]] = {}
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue

        if ":" not in entry:
            logger.warning(
                f"Invalid ADMIN_ROLES entry (missing colon separator), skipped: {entry}"
            )
            continue

        user_part, roles_part = entry.split(":", 1)
        user_part = user_part.strip()
        roles_part = roles_part.strip()

        try:
            user_id = validate_uuid(user_part, "admin_role_user")
        except ValueError as e:
            logger.warning(f"Invalid user ID in ADMIN_ROLES, skipped: {e}")
            continue

        valid_roles: set[str] = set()
        for role_name in roles_part.split(","):
            role_name = role_name.strip()
            if not role_name:
                continue
            if role_name in _ALL_ROLES:
                valid_roles.add(role_name)
            else:
                logger.warning(
                    f"Unknown role '{role_name}' in ADMIN_ROLES for user "
                    f"{user_id[:8]}..., skipped"
                )

        if valid_roles:
            result[user_id] = valid_roles

    return result


def get_legacy_admin_ids() -> set[str]:
    """Get validated admin IDs from legacy ADMIN_USER_IDS env var.

    Legacy admin IDs get the DASHBOARD role only (minimum privilege)
    to maintain backward compatibility while enforcing least privilege.

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


def get_user_roles_from_env(user_id: str) -> set[str] | None:
    """Resolve admin roles for a user exclusively from environment variables.

    Resolution order (first match wins):
    1. MASTER_USER_IDS -> all roles (if user is in master list)
    2. ADMIN_ROLES -> explicit role mapping (if user has mapped roles)
    3. ADMIN_USER_IDS -> DASHBOARD only (legacy fallback)

    Returns None if no roles found in any env var.
    The caller should check the admin_roles table in Supabase as fallback.
    """
    uid = user_id.lower()

    # 1. Check MASTER_USER_IDS (highest priority — all roles)
    if uid in get_master_ids():
        return set(_ALL_ROLES)

    # 2. Check ADMIN_ROLES (explicit mapping)
    admin_roles = parse_admin_roles()
    if uid in admin_roles:
        return admin_roles[uid]

    # 3. Check legacy ADMIN_USER_IDS (minimum privilege — DASHBOARD only)
    if uid in get_legacy_admin_ids():
        return {AdminRole.DASHBOARD.value}

    return None
