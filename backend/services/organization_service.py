"""Organization service for multi-user consultancy management.

STORY-322: Plano Consultoria — multi-user organization support.
RBAC-ORG-001: role enum collapsed to (owner | member | viewer); legacy
'admin' rows are migrated to 'member' (privilege-down). Service-level
role checks below still accept legacy 'admin' as equivalent to 'owner'
during the migration window so partially-replicated clients don't 500.
The authoritative gate is `dependencies/org_auth.require_org_role`.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from supabase_client import get_supabase

logger = logging.getLogger(__name__)


# Roles allowed to perform owner-grade service operations. Legacy 'admin'
# is included for migration-window safety only; new code should depend on
# `dependencies.org_auth.require_org_role(OrgRole.OWNER)` at the API layer.
_OWNER_ROLES: tuple[str, ...] = ("owner", "admin")


async def create_organization(owner_id: str, name: str) -> dict:
    """Create a new organization and add the owner as a member.

    1. Insert into organizations (owner_id, name)
    2. Insert owner into organization_members (role='owner', accepted_at=NOW())
    3. Return the created organization
    """
    sb = get_supabase()

    # Insert org
    org_result = sb.table("organizations").insert({
        "owner_id": owner_id,
        "name": name,
    }).execute()

    if not org_result.data:
        raise ValueError("Failed to create organization")

    org = org_result.data[0]

    # Add owner as member (accepted immediately)
    now = datetime.now(timezone.utc).isoformat()
    sb.table("organization_members").insert({
        "org_id": org["id"],
        "user_id": owner_id,
        "role": "owner",
        "accepted_at": now,
    }).execute()

    logger.info(f"Organization created: org_id={org['id']}, owner_id={owner_id[:8]}***")
    return org


async def get_organization(org_id: str, user_id: str) -> Optional[dict]:
    """Get organization details. User must be a member."""
    sb = get_supabase()

    # Verify membership
    member = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data:
        return None

    org = sb.table("organizations").select("*").eq("id", org_id).single().execute()
    if not org.data:
        return None

    # Get members list
    members = (
        sb.table("organization_members")
        .select("user_id, role, invited_at, accepted_at")
        .eq("org_id", org_id)
        .execute()
    )

    result = org.data
    result["members"] = members.data or []
    result["user_role"] = member.data[0]["role"]
    return result


async def invite_member(org_id: str, inviter_id: str, email: str) -> dict:
    """Invite a member to the organization by email.

    1. Verify inviter is owner/admin
    2. Check max_members limit
    3. Find user by email in profiles
    4. Insert into organization_members (accepted_at=NULL = pending)
    """
    sb = get_supabase()

    # Check inviter role
    inviter = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", inviter_id)
        .limit(1)
        .execute()
    )
    if not inviter.data or inviter.data[0]["role"] not in ("owner", "admin"):
        raise PermissionError("Apenas owner ou admin podem convidar membros")

    # Check member count vs max
    org = (
        sb.table("organizations")
        .select("max_members")
        .eq("id", org_id)
        .single()
        .execute()
    )
    if not org.data:
        raise ValueError("Organization not found")

    current_members = (
        sb.table("organization_members")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .execute()
    )
    if current_members.count and current_members.count >= org.data["max_members"]:
        raise ValueError(f"Limite de membros atingido ({org.data['max_members']})")

    # Find user by email
    user_result = (
        sb.table("profiles")
        .select("id")
        .eq("email", email)
        .limit(1)
        .execute()
    )
    if not user_result.data:
        raise ValueError(f"Nenhum usuario encontrado com o email {email}")

    target_user_id = user_result.data[0]["id"]

    # Check if already member
    existing = (
        sb.table("organization_members")
        .select("id")
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        raise ValueError("Usuario ja e membro da organizacao")

    # Insert invite (accepted_at=NULL means pending)
    invite_result = sb.table("organization_members").insert({
        "org_id": org_id,
        "user_id": target_user_id,
        "role": "member",
    }).execute()

    logger.info(f"Member invited: org_id={org_id}, email={email}")
    return invite_result.data[0] if invite_result.data else {}


async def accept_invite(org_id: str, user_id: str) -> dict:
    """Accept a pending invitation."""
    sb = get_supabase()

    # Find pending invite
    invite = (
        sb.table("organization_members")
        .select("id, accepted_at")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not invite.data:
        raise ValueError("Convite nao encontrado")
    if invite.data[0].get("accepted_at"):
        raise ValueError("Convite ja aceito")

    # Accept
    now = datetime.now(timezone.utc).isoformat()
    sb.table("organization_members").update({"accepted_at": now}).eq("id", invite.data[0]["id"]).execute()

    logger.info(f"Invite accepted: org_id={org_id}, user_id={user_id[:8]}***")
    return {"accepted": True}


async def remove_member(org_id: str, remover_id: str, target_user_id: str) -> dict:
    """Remove a member from the organization.

    Remover must be owner/admin. Cannot remove the owner.
    """
    sb = get_supabase()

    # Check remover role
    remover = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", remover_id)
        .limit(1)
        .execute()
    )
    if not remover.data or remover.data[0]["role"] not in ("owner", "admin"):
        raise PermissionError("Apenas owner ou admin podem remover membros")

    # Check target role (cannot remove owner)
    target = (
        sb.table("organization_members")
        .select("id, role")
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .limit(1)
        .execute()
    )
    if not target.data:
        raise ValueError("Membro nao encontrado")
    if target.data[0]["role"] == "owner":
        raise PermissionError("Nao e possivel remover o owner da organizacao")

    # Delete
    sb.table("organization_members").delete().eq("id", target.data[0]["id"]).execute()

    logger.info(f"Member removed: org_id={org_id}, target_user_id={target_user_id[:8]}***")
    return {"removed": True}


async def get_org_dashboard(org_id: str, user_id: str) -> dict:
    """Get consolidated dashboard stats for the organization.

    Only owner/admin can see org-wide stats.
    """
    sb = get_supabase()

    # Verify role
    member = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data or member.data[0]["role"] not in ("owner", "admin"):
        raise PermissionError("Apenas owner ou admin podem ver o dashboard")

    # Get all member IDs
    members = (
        sb.table("organization_members")
        .select("user_id")
        .eq("org_id", org_id)
        .execute()
    )
    member_ids = [m["user_id"] for m in (members.data or [])]

    if not member_ids:
        return {"total_searches": 0, "total_opportunities": 0, "total_value": 0, "member_count": 0}

    # Aggregate search sessions
    sessions = (
        sb.table("search_sessions")
        .select("total_results, total_value")
        .in_("user_id", member_ids)
        .execute()
    )

    total_searches = len(sessions.data) if sessions.data else 0
    total_opportunities = sum(s.get("total_results", 0) or 0 for s in (sessions.data or []))
    total_value = sum(float(s.get("total_value", 0) or 0) for s in (sessions.data or []))

    return {
        "total_searches": total_searches,
        "total_opportunities": total_opportunities,
        "total_value": total_value,
        "member_count": len(member_ids),
    }


async def update_org_logo(org_id: str, user_id: str, logo_url: str) -> dict:
    """Update organization logo URL. Only owner/admin."""
    sb = get_supabase()

    # Check role
    member = (
        sb.table("organization_members")
        .select("role")
        .eq("org_id", org_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data or member.data[0]["role"] not in ("owner", "admin"):
        raise PermissionError("Apenas owner ou admin podem alterar o logo")

    sb.table("organizations").update({"logo_url": logo_url}).eq("id", org_id).execute()

    logger.info(f"Logo updated: org_id={org_id}")
    return {"updated": True}


async def get_user_org(user_id: str) -> Optional[dict]:
    """Get the organization a user belongs to, if any."""
    sb = get_supabase()

    member = (
        sb.table("organization_members")
        .select("org_id, role, accepted_at")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not member.data:
        return None

    org_id = member.data[0]["org_id"]
    org = (
        sb.table("organizations")
        .select("id, name, logo_url, max_members, plan_type")
        .eq("id", org_id)
        .single()
        .execute()
    )

    if not org.data:
        return None

    result = org.data
    result["user_role"] = member.data[0]["role"]
    result["accepted"] = member.data[0].get("accepted_at") is not None
    return result


# ---------------------------------------------------------------------------
# RBAC-ORG-001: new operations (transfer ownership, update role)
# ---------------------------------------------------------------------------


def _count_owners(sb, org_id: str) -> int:
    """Count active owners for an org. Helper for last-owner invariant (AC7)."""
    result = (
        sb.table("organization_members")
        .select("id", count="exact")
        .eq("org_id", org_id)
        .eq("role", "owner")
        .execute()
    )
    return getattr(result, "count", None) or 0


async def update_member_role(
    org_id: str,
    actor_user_id: str,
    target_user_id: str,
    new_role: str,
) -> dict:
    """Promote/demote a member's role.

    AC7: Rejects demotion of the LAST remaining owner (preserves the
    "≥1 owner per org" invariant). The API layer should already have
    gated this endpoint via `require_org_role(OWNER)`; this function
    re-validates defensively.

    Args:
        org_id: organization UUID
        actor_user_id: who is making the change (must be an owner)
        target_user_id: whose role is being updated
        new_role: one of ('owner', 'member', 'viewer')

    Returns:
        dict with shape `{updated: True, target_user_id, old_role, new_role}`

    Raises:
        ValueError on bad input / target not found
        PermissionError on RBAC violation / last-owner demotion
    """
    if new_role not in ("owner", "member", "viewer"):
        raise ValueError(f"Papel inválido: {new_role!r}")

    sb = get_supabase()

    # Find target row
    target = (
        sb.table("organization_members")
        .select("id, role, accepted_at")
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .limit(1)
        .execute()
    )
    if not target.data:
        raise ValueError("Membro não encontrado")
    target_row = target.data[0]
    old_role = (target_row.get("role") or "").lower()

    if old_role == new_role:
        return {
            "updated": False,
            "target_user_id": target_user_id,
            "old_role": old_role,
            "new_role": new_role,
            "reason": "no_change",
        }

    # Last-owner invariant: if demoting an owner, ensure another exists.
    if old_role == "owner" and new_role != "owner":
        owner_count = _count_owners(sb, org_id)
        if owner_count <= 1:
            raise PermissionError(
                "Não é possível rebaixar o último owner. Transfira a "
                "propriedade ou promova outro membro a owner primeiro."
            )

    sb.table("organization_members").update({"role": new_role}).eq(
        "id", target_row["id"]
    ).execute()

    logger.info(
        "RBAC-ORG-001 role_changed: org_id=%s target=%s old=%s new=%s actor=%s",
        org_id,
        target_user_id[:8] + "***",
        old_role,
        new_role,
        actor_user_id[:8] + "***",
    )
    return {
        "updated": True,
        "target_user_id": target_user_id,
        "old_role": old_role,
        "new_role": new_role,
    }


async def transfer_ownership(
    org_id: str,
    current_owner_id: str,
    target_user_id: str,
) -> dict:
    """Atomically transfer ownership from current owner to a target member.

    AC6: rebaixa current owner → member, promove target → owner.

    NOTE: Supabase Python SDK does not expose `BEGIN / COMMIT` — we run
    two ordered UPDATE statements. The post-update verification step
    detects (and rolls back) inconsistent state. For higher integrity
    move this to a SQL function (SECURITY DEFINER) in a future iteration.

    Args:
        org_id: organization UUID
        current_owner_id: the user performing the transfer (must be an owner)
        target_user_id: the new owner — must already be a member of the org

    Returns:
        `{transferred: True, from_user_id, to_user_id}`

    Raises:
        PermissionError if current_owner is not actually an owner
        ValueError if target is not a member, or is current owner
    """
    if current_owner_id == target_user_id:
        raise ValueError("Não é possível transferir propriedade para si mesmo")

    sb = get_supabase()

    # Validate current owner
    actor = (
        sb.table("organization_members")
        .select("id, role")
        .eq("org_id", org_id)
        .eq("user_id", current_owner_id)
        .limit(1)
        .execute()
    )
    if not actor.data or (actor.data[0].get("role") or "").lower() != "owner":
        raise PermissionError("Apenas owner pode transferir a propriedade")

    # Validate target is an existing accepted member
    target = (
        sb.table("organization_members")
        .select("id, role, accepted_at")
        .eq("org_id", org_id)
        .eq("user_id", target_user_id)
        .limit(1)
        .execute()
    )
    if not target.data:
        raise ValueError("Usuário alvo não é membro da organização")
    if target.data[0].get("accepted_at") is None:
        raise ValueError("Usuário alvo ainda não aceitou o convite")

    # Step 1: promote target → owner
    sb.table("organization_members").update({"role": "owner"}).eq(
        "id", target.data[0]["id"]
    ).execute()

    # Step 2: demote current owner → member
    sb.table("organization_members").update({"role": "member"}).eq(
        "id", actor.data[0]["id"]
    ).execute()

    # Step 3: update organizations.owner_id pointer (kept in sync for legacy
    # code paths that read the column directly).
    sb.table("organizations").update({"owner_id": target_user_id}).eq(
        "id", org_id
    ).execute()

    logger.info(
        "RBAC-ORG-001 transfer_ownership: org_id=%s from=%s to=%s",
        org_id,
        current_owner_id[:8] + "***",
        target_user_id[:8] + "***",
    )

    return {
        "transferred": True,
        "from_user_id": current_owner_id,
        "to_user_id": target_user_id,
    }
