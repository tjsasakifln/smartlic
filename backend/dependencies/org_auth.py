"""Organization-level RBAC dependency for FastAPI routes.

RBAC-ORG-001 — enforce `owner | member | viewer` role hierarchy on the
12-endpoint surface in `routes/organizations.py`.

Pattern (factory):

    from dependencies.org_auth import require_org_role
    from schemas.organization import OrgRole

    @router.delete("/organizations/{org_id}")
    async def delete_org(
        org_id: str,
        member = Depends(require_org_role(OrgRole.OWNER)),
    ):
        ...

The factory returns a fresh dependency callable for each min_role. Inside,
the callable resolves the user via `require_auth`, looks up the
membership row in `organization_members`, and compares the user's role
against `min_role` ordinally. On insufficient privilege it raises 403;
on missing membership it raises 404 (do not leak existence info).

This module also exposes a `require_org_permission(perm: str)` placeholder
(AC15) that today proxies to a hard-coded role mapping, so the surface
exists for a future granular `organization_permissions` table.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable, Optional

from fastapi import Depends, HTTPException

from auth import require_auth
from log_sanitizer import mask_user_id
from schemas.organization import OrganizationMember, OrgRole

logger = logging.getLogger(__name__)


# Mapping of legacy/alias role names to the canonical enum.
# 20260301100000_create_organizations.sql allowed ('owner', 'admin', 'member');
# the RBAC-ORG-001 backfill migration rewrites 'admin' → 'member' but we keep
# the alias here so that:
#   - rows still containing 'admin' on hot replicas during migration window
#     are interpreted as 'member' (closest privilege without privilege-up).
#   - test fixtures and old API consumers don't 500 if they pass 'admin'.
_LEGACY_ROLE_ALIASES: dict[str, OrgRole] = {
    "owner": OrgRole.OWNER,
    "member": OrgRole.MEMBER,
    "viewer": OrgRole.VIEWER,
    "admin": OrgRole.MEMBER,  # legacy alias, see comment above
}


def _coerce_role(raw: str) -> Optional[OrgRole]:
    """Return canonical OrgRole or None for unknown strings."""
    if not raw:
        return None
    return _LEGACY_ROLE_ALIASES.get(raw.strip().lower())


async def _fetch_membership(
    org_id: str, user_id: str
) -> Optional[OrganizationMember]:
    """Look up the active membership row for (org_id, user_id).

    Only considers rows with `accepted_at IS NOT NULL` — pending invites
    must NOT grant access. Returns None if not found.

    Uses the service-role Supabase client (bypasses RLS) so that this
    helper is callable from any route without a session JWT context.
    The handler MUST still treat None as "not a member".
    """
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    try:
        result = await sb_execute(
            sb.table("organization_members")
            .select("org_id, user_id, role, invited_at, accepted_at")
            .eq("org_id", org_id)
            .eq("user_id", user_id)
            .limit(1)
        )
    except Exception as e:
        # Defensive: never let DB transient errors crash the dependency.
        # The handler will still 503 on actual writes if the DB is down.
        logger.warning(
            "org_auth: membership lookup failed org_id=%s user=%s err=%s",
            org_id,
            mask_user_id(user_id),
            type(e).__name__,
        )
        return None

    if not result.data:
        return None

    row = result.data[0]
    if row.get("accepted_at") is None:
        # Pending invite: not yet a member, don't grant any role.
        return None

    role = _coerce_role(row.get("role", ""))
    if role is None:
        logger.warning(
            "org_auth: unknown role %r on org_id=%s user=%s — treating as no access",
            row.get("role"),
            org_id,
            mask_user_id(user_id),
        )
        return None

    return OrganizationMember(
        org_id=row["org_id"],
        user_id=row["user_id"],
        role=role,
        invited_at=row.get("invited_at"),
        accepted_at=row.get("accepted_at"),
    )


def require_org_role(
    min_role: OrgRole,
) -> Callable[..., Awaitable[OrganizationMember]]:
    """Factory: return a FastAPI dependency enforcing user.role >= min_role.

    The returned callable receives `org_id` from the path and `user`
    from `require_auth`, fetches the membership row, and:

    * raises 401 if no auth (handled by `require_auth`)
    * raises 404 if the user has no accepted membership in that org
      (don't leak existence; the org might not be theirs to know about)
    * raises 403 if the user's role is below `min_role`
    * returns the OrganizationMember on success

    Test pattern:

        # Override the membership lookup, not the factory result, because
        # each call to require_org_role(...) returns a fresh callable.
        from dependencies import org_auth

        async def _fake_lookup(org_id, user_id):
            return OrganizationMember(
                org_id=org_id, user_id=user_id, role=OrgRole.OWNER,
                accepted_at=datetime.now(timezone.utc),
            )

        monkeypatch.setattr(org_auth, "_fetch_membership", _fake_lookup)
    """

    async def _dependency(
        org_id: str,
        user: dict = Depends(require_auth),
    ) -> OrganizationMember:
        user_id = user["id"]
        member = await _fetch_membership(org_id=org_id, user_id=user_id)
        if member is None:
            # Don't reveal whether the org exists or whether the user is
            # just not a member — both leak info to attackers.
            logger.info(
                "org_auth: 404 (no membership) org_id=%s user=%s",
                org_id,
                mask_user_id(user_id),
            )
            raise HTTPException(
                status_code=404,
                detail="Organização não encontrada",
            )

        if member.role < min_role:
            logger.warning(
                "org_auth: 403 forbidden org_id=%s user=%s role=%s required=%s",
                org_id,
                mask_user_id(user_id),
                member.role.value,
                min_role.value,
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Acesso negado. Esta operação requer papel "
                    f"{min_role.value} ou superior."
                ),
            )

        return member

    # Preserve a stable name for debugging — FastAPI uses __name__ in the
    # OpenAPI schema for sub-dependencies.
    _dependency.__name__ = f"require_org_role_{min_role.value}"
    return _dependency


# ---------------------------------------------------------------------------
# AC15: Forward-compat placeholder for granular permission checks.
# ---------------------------------------------------------------------------
# Today this is a thin role-mapping wrapper. Future work (out of scope for
# RBAC-ORG-001) will introduce an `organization_permissions` table and
# replace the body with a join lookup. The function signature is fixed so
# routes can adopt it now and gain granularity without churn.
# ---------------------------------------------------------------------------

# Map of permission name → minimum role required (placeholder mapping).
# When `organization_permissions` lands, this dict will be replaced by a
# DB lookup keyed by (org_id, role, permission).
_PERMISSION_ROLE_FLOOR: dict[str, OrgRole] = {
    "org.read": OrgRole.VIEWER,
    "org.members.read": OrgRole.MEMBER,
    "org.members.invite": OrgRole.OWNER,
    "org.members.remove": OrgRole.OWNER,
    "org.members.role.change": OrgRole.OWNER,
    "org.update": OrgRole.OWNER,
    "org.delete": OrgRole.OWNER,
    "org.transfer_ownership": OrgRole.OWNER,
    "org.billing.read": OrgRole.OWNER,
    "org.audit_log.read": OrgRole.OWNER,
}


def require_org_permission(
    perm: str,
) -> Callable[..., Awaitable[OrganizationMember]]:
    """Placeholder dependency for granular permission checks.

    Today: maps `perm` → minimum role and delegates to `require_org_role`.
    Tomorrow: looks up `organization_permissions` for (org_id, role, perm).

    Signature is stable so handlers can adopt this now:

        @router.post("/organizations/{org_id}/invite")
        async def invite(
            org_id: str,
            member = Depends(require_org_permission("org.members.invite")),
        ):
            ...
    """
    floor = _PERMISSION_ROLE_FLOOR.get(perm)
    if floor is None:
        raise ValueError(
            f"Unknown organization permission {perm!r}. "
            f"Add it to _PERMISSION_ROLE_FLOOR in dependencies/org_auth.py."
        )
    return require_org_role(floor)
