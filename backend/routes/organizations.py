"""Organization routes for multi-user consultancy management.

STORY-322: Plano Consultoria — organization CRUD and member management.
STORY-331 AC3: Defensive guard — PGRST205 → HTTP 503.
RBAC-ORG-001: every mutating endpoint is gated by `require_org_role(...)`
              with the enterprise matrix from
              docs/adr/ADR-RBAC-ORG-001-enterprise-standard.md.

Endpoint matrix (11 total — 8 legacy + 3 new):

| Endpoint                                                | Min role            |
|---------------------------------------------------------|---------------------|
| GET    /v1/organizations/me                             | (auth)              |
| POST   /v1/organizations                                | (auth)              |
| GET    /v1/organizations/{org_id}                       | viewer              |
| POST   /v1/organizations/{org_id}/invite                | owner               |
| POST   /v1/organizations/{org_id}/accept                | (invitee — token)   |
| DELETE /v1/organizations/{org_id}/members/{target_id}   | owner OR self-leave |
| GET    /v1/organizations/{org_id}/dashboard             | member              |
| PUT    /v1/organizations/{org_id}/logo                  | owner               |
| PATCH  /v1/organizations/{org_id}/members/{user_id}/role| owner               |
| POST   /v1/organizations/{org_id}/transfer-ownership    | owner               |
| GET    /v1/organizations/{org_id}/audit-log             | owner               |

Endpoints from the original 12-row matrix that are NOT in this file
(PATCH org, DELETE org, GET billing, POST checkout) are intentionally
deferred — see story Change Log entry 2026-04-28. They were in the
matrix but not in the explicit AC list; deferring keeps the security
fix shippable in one PR.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import require_auth
from config import ORGANIZATIONS_ENABLED
from dependencies.org_auth import require_org_role
from log_sanitizer import mask_user_id
from schemas.organization import (
    OrganizationAuditLogResponse,
    OrganizationMember,
    OrgRole,
    TransferOwnershipRequest,
    UpdateMemberRoleRequest,
)
from services.organization_audit import fetch_audit_log, log_org_event
from services.organization_service import (
    accept_invite,
    create_organization,
    get_org_dashboard,
    get_organization,
    get_user_org,
    invite_member,
    remove_member,
    transfer_ownership,
    update_member_role,
    update_org_logo,
)
from supabase_client import _is_schema_error

logger = logging.getLogger(__name__)

router = APIRouter(tags=["organizations"])


# ── Request body schemas ──────────────────────────────────────────────────────


class CreateOrgRequest(BaseModel):
    name: str


class InviteMemberRequest(BaseModel):
    email: str


class UpdateLogoRequest(BaseModel):
    logo_url: str


# ── Routes ────────────────────────────────────────────────────────────────────

# IMPORTANT: /organizations/me MUST be declared BEFORE /organizations/{org_id}
# to prevent FastAPI from treating "me" as an org_id path parameter.


# Helper: GET /v1/organizations/me — get current user's org
@router.get("/organizations/me")
async def get_my_org(
    user: dict = Depends(require_auth),
):
    """Get the organization the current user belongs to."""
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    user_id = user["id"]
    logger.debug("get_my_org user=%s", mask_user_id(user_id))
    try:
        org = await get_user_org(user_id=user_id)
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        raise
    if not org:
        return {"organization": None}
    return {"organization": org}


# AC11: POST /v1/organizations — create org (any authenticated user; creator is owner)
@router.post("/organizations", status_code=201)
async def create_org(
    body: CreateOrgRequest,
    user: dict = Depends(require_auth),
):
    """Create organization (owner = current user)."""
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    user_id = user["id"]
    logger.info("create_org user=%s name=%r", mask_user_id(user_id), body.name)
    try:
        org = await create_organization(owner_id=user_id, name=body.name)
        return org
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        logger.error("Failed to create organization user=%s: %s", mask_user_id(user_id), e)
        raise HTTPException(status_code=500, detail="Erro ao criar organizacao")


# AC12: GET /v1/organizations/{org_id} — org details (RBAC: viewer+)
@router.get("/organizations/{org_id}")
async def get_org(
    org_id: str,
    member: OrganizationMember = Depends(require_org_role(OrgRole.VIEWER)),
):
    """Get organization details (any accepted member)."""
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    user_id = member.user_id
    logger.debug("get_org org_id=%s user=%s", org_id, mask_user_id(user_id))
    try:
        org = await get_organization(org_id=org_id, user_id=user_id)
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        raise
    if not org:
        raise HTTPException(status_code=404, detail="Organizacao nao encontrada")
    return org


# AC13: POST /v1/organizations/{org_id}/invite — invite member (RBAC: owner)
@router.post("/organizations/{org_id}/invite")
async def invite_org_member(
    org_id: str,
    body: InviteMemberRequest,
    member: OrganizationMember = Depends(require_org_role(OrgRole.OWNER)),
):
    """Invite a member to the organization (owner only)."""
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    user_id = member.user_id
    logger.info(
        "invite_org_member org_id=%s inviter=%s email=%r",
        org_id,
        mask_user_id(user_id),
        body.email,
    )
    try:
        result = await invite_member(org_id=org_id, inviter_id=user_id, email=body.email)
        await log_org_event(
            org_id=org_id,
            actor_user_id=user_id,
            action="invite_sent",
            new_value=body.email,
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        logger.error(
            "Failed to invite member org_id=%s inviter=%s: %s",
            org_id,
            mask_user_id(user_id),
            e,
        )
        raise HTTPException(status_code=500, detail="Erro ao convidar membro")


# AC14: POST /v1/organizations/{org_id}/accept — accept invite (invitee via auth)
@router.post("/organizations/{org_id}/accept")
async def accept_org_invite(
    org_id: str,
    user: dict = Depends(require_auth),
):
    """Accept a pending organization invite.

    NB: invitee may not yet be a member (`accepted_at IS NULL`), so we
    cannot use `require_org_role` here — the dependency would 404.
    Authorization is by holding a valid pending invite row, validated
    inside `accept_invite`.
    """
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    user_id = user["id"]
    logger.info("accept_org_invite org_id=%s user=%s", org_id, mask_user_id(user_id))
    try:
        result = await accept_invite(org_id=org_id, user_id=user_id)
        await log_org_event(
            org_id=org_id,
            actor_user_id=user_id,
            action="invite_accepted",
            target_user_id=user_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        logger.error(
            "Failed to accept invite org_id=%s user=%s: %s",
            org_id,
            mask_user_id(user_id),
            e,
        )
        raise HTTPException(status_code=500, detail="Erro ao aceitar convite")


# AC15: DELETE /v1/organizations/{org_id}/members/{target_user_id} — remove member
# RBAC: owner can remove anyone; member/viewer can only remove themselves (leave).
@router.delete("/organizations/{org_id}/members/{target_user_id}")
async def remove_org_member(
    org_id: str,
    target_user_id: str,
    member: OrganizationMember = Depends(require_org_role(OrgRole.VIEWER)),
):
    """Remove a member from the organization.

    - Owner: may remove any member, but cannot remove the last owner
      (enforced inside `remove_member`).
    - Member / viewer: may ONLY remove themselves (self-leave). Attempts
      to remove someone else 403.
    """
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    actor_id = member.user_id

    is_self = actor_id == target_user_id
    is_owner = member.role == OrgRole.OWNER
    if not is_self and not is_owner:
        logger.info(
            "remove_org_member 403 (non-owner non-self) org_id=%s actor=%s target=%s",
            org_id,
            mask_user_id(actor_id),
            mask_user_id(target_user_id),
        )
        raise HTTPException(
            status_code=403,
            detail="Apenas owners podem remover outros membros.",
        )

    logger.info(
        "remove_org_member org_id=%s remover=%s target=%s",
        org_id,
        mask_user_id(actor_id),
        mask_user_id(target_user_id),
    )
    try:
        result = await remove_member(
            org_id=org_id,
            remover_id=actor_id,
            target_user_id=target_user_id,
        )
        await log_org_event(
            org_id=org_id,
            actor_user_id=actor_id,
            action="member_left" if is_self else "member_removed",
            target_user_id=target_user_id,
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        logger.error(
            "Failed to remove member org_id=%s remover=%s target=%s: %s",
            org_id,
            mask_user_id(actor_id),
            mask_user_id(target_user_id),
            e,
        )
        raise HTTPException(status_code=500, detail="Erro ao remover membro")


# AC16: GET /v1/organizations/{org_id}/dashboard — consolidated stats (RBAC: member+)
@router.get("/organizations/{org_id}/dashboard")
async def get_org_dashboard_endpoint(
    org_id: str,
    member: OrganizationMember = Depends(require_org_role(OrgRole.MEMBER)),
):
    """Get consolidated dashboard for organization (member+ — viewers see nothing)."""
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    user_id = member.user_id
    logger.debug("get_org_dashboard org_id=%s user=%s", org_id, mask_user_id(user_id))
    try:
        result = await get_org_dashboard(org_id=org_id, user_id=user_id)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        logger.error(
            "Failed to get org dashboard org_id=%s user=%s: %s",
            org_id,
            mask_user_id(user_id),
            e,
        )
        raise HTTPException(status_code=500, detail="Erro ao obter dashboard da organizacao")


# AC17: PUT /v1/organizations/{org_id}/logo — update logo URL (RBAC: owner)
@router.put("/organizations/{org_id}/logo")
async def upload_org_logo(
    org_id: str,
    body: UpdateLogoRequest,
    member: OrganizationMember = Depends(require_org_role(OrgRole.OWNER)),
):
    """Update organization logo URL (owner only).

    Note: Actual file upload to Supabase Storage is handled client-side.
    This endpoint receives the public storage URL after the client-side upload.
    """
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    user_id = member.user_id
    logger.info("upload_org_logo org_id=%s user=%s", org_id, mask_user_id(user_id))
    try:
        result = await update_org_logo(org_id=org_id, user_id=user_id, logo_url=body.logo_url)
        await log_org_event(
            org_id=org_id,
            actor_user_id=user_id,
            action="logo_updated",
            new_value=body.logo_url,
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        logger.error(
            "Failed to update org logo org_id=%s user=%s: %s",
            org_id,
            mask_user_id(user_id),
            e,
        )
        raise HTTPException(status_code=500, detail="Erro ao atualizar logo da organizacao")


# AC7: PATCH /v1/organizations/{org_id}/members/{target_user_id}/role — promote/demote
@router.patch("/organizations/{org_id}/members/{target_user_id}/role")
async def update_org_member_role(
    org_id: str,
    target_user_id: str,
    body: UpdateMemberRoleRequest,
    member: OrganizationMember = Depends(require_org_role(OrgRole.OWNER)),
):
    """Promote/demote a member's role (owner only).

    Rejects demotion of the last remaining owner (preserves the
    "≥1 owner per org" invariant — story AC7).
    """
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    actor_id = member.user_id
    new_role = body.role.value
    logger.info(
        "update_org_member_role org_id=%s actor=%s target=%s new_role=%s",
        org_id,
        mask_user_id(actor_id),
        mask_user_id(target_user_id),
        new_role,
    )
    try:
        result = await update_member_role(
            org_id=org_id,
            actor_user_id=actor_id,
            target_user_id=target_user_id,
            new_role=new_role,
        )
        if result.get("updated"):
            await log_org_event(
                org_id=org_id,
                actor_user_id=actor_id,
                action="role_changed",
                target_user_id=target_user_id,
                old_value=result.get("old_role"),
                new_value=result.get("new_role"),
            )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        logger.error(
            "Failed to update member role org_id=%s actor=%s target=%s: %s",
            org_id,
            mask_user_id(actor_id),
            mask_user_id(target_user_id),
            e,
        )
        raise HTTPException(status_code=500, detail="Erro ao atualizar papel do membro")


# AC6: POST /v1/organizations/{org_id}/transfer-ownership
@router.post("/organizations/{org_id}/transfer-ownership")
async def transfer_org_ownership(
    org_id: str,
    body: TransferOwnershipRequest,
    member: OrganizationMember = Depends(require_org_role(OrgRole.OWNER)),
):
    """Transfer ownership atomically. Current owner becomes member; target
    must already be a member; target becomes new owner.

    Two-step UI confirmation enforced by `body.confirm` flag (AC11 frontend).
    """
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")
    if not body.confirm:
        raise HTTPException(
            status_code=400,
            detail="Confirmação obrigatória: envie {'confirm': true}.",
        )
    actor_id = member.user_id
    target = body.target_user_id

    logger.info(
        "transfer_org_ownership org_id=%s from=%s to=%s",
        org_id,
        mask_user_id(actor_id),
        mask_user_id(target),
    )
    try:
        result = await transfer_ownership(
            org_id=org_id,
            current_owner_id=actor_id,
            target_user_id=target,
        )
        await log_org_event(
            org_id=org_id,
            actor_user_id=actor_id,
            action="transfer_ownership",
            target_user_id=target,
            old_value=actor_id,
            new_value=target,
        )
        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        logger.error(
            "Failed transfer ownership org_id=%s actor=%s target=%s: %s",
            org_id,
            mask_user_id(actor_id),
            mask_user_id(target),
            e,
        )
        raise HTTPException(status_code=500, detail="Erro ao transferir propriedade")


# AC9: GET /v1/organizations/{org_id}/audit-log — paginated audit log (owner only)
@router.get(
    "/organizations/{org_id}/audit-log",
    response_model=OrganizationAuditLogResponse,
)
async def get_org_audit_log(
    org_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_org_role(OrgRole.OWNER)),
):
    """Paginated audit log for the organization (owner only)."""
    if not ORGANIZATIONS_ENABLED:
        raise HTTPException(status_code=404, detail="Feature not available")

    logger.debug(
        "get_org_audit_log org_id=%s actor=%s limit=%d offset=%d",
        org_id,
        mask_user_id(member.user_id),
        limit,
        offset,
    )
    try:
        rows, total = await fetch_audit_log(org_id=org_id, limit=limit, offset=offset)
        # Pydantic v2 model_validate coerces dicts → OrganizationAuditLogEntry.
        return OrganizationAuditLogResponse.model_validate(
            {
                "entries": rows,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        )
    except Exception as e:
        if _is_schema_error(e):
            raise HTTPException(status_code=503, detail="Feature not yet available")
        logger.error(
            "Failed to fetch audit log org_id=%s: %s",
            org_id,
            e,
        )
        raise HTTPException(status_code=500, detail="Erro ao obter auditoria")
