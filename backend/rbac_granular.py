"""RBAC Granular Phase 1 (#1912)."""
from fastapi import Depends, HTTPException

_ALL_ADMIN_ROLES = {"admin:users","admin:billing","admin:cache","admin:partners","admin:seo","admin:ops","admin:compliance","admin:super"}

async def get_profile_admin_roles(user_id):
    try:
        from supabase_client import get_supabase, sb_execute
        sb = get_supabase()
        result = await sb_execute(sb.table("profiles").select("admin_roles").eq("id", user_id).single(), category="read")
        if result.data:
            return list(result.data.get("admin_roles", []) or [])
    except Exception: pass
    return []

def require_admin_role(role):
    from auth import require_auth as _ra
    if role not in _ALL_ADMIN_ROLES: raise ValueError(f"Unknown admin role: {role}")
    async def _checker(user=Depends(_ra)):
        ur = await get_profile_admin_roles(user["id"])
        if "admin:super" not in ur and role not in ur:
            raise HTTPException(403, detail="Permissao insuficiente: requer role " + role)
        return user
    return _checker

require_admin_users = require_admin_role("admin:users")
require_admin_billing = require_admin_role("admin:billing")
require_admin_cache = require_admin_role("admin:cache")
require_admin_partners = require_admin_role("admin:partners")
require_admin_seo = require_admin_role("admin:seo")
require_admin_ops = require_admin_role("admin:ops")
require_admin_compliance = require_admin_role("admin:compliance")
require_admin_super = require_admin_role("admin:super")

def has_admin_role(roles, role):
    return "admin:super" in roles or role in roles
