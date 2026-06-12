"""CONSULT-001 (#1613): Consultant Seats — consultant-client management endpoints.

Endpoints for the Consultoria plan (R$997/mes) to invite clients, manage
relationships, share resources, and control access.

Feature flag: CONSULTANT_SEATS_ENABLED (config/features.py)
"""

import logging
import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from auth import require_auth
from config.features import get_feature_flag
from schemas.consultoria import (
    ConsultantClientListResponse,
    ConsultantClientResponse,
    ConsultantInviteResponse,
    ConsultantShareCreate,
    ConsultantShareResponse,
    InviteClientRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["consultoria"])

# Maximum active client seats per consultant
MAX_CLIENT_SEATS = 10
# Invite link expiry in days
INVITE_LINK_EXPIRY_DAYS = 7

# In-memory invite store (in production, use Redis/DB)
_invite_store: dict[str, dict] = {}


async def _verify_consultant_access(user_id: str) -> tuple:
    """Verify the user has an active Consultoria subscription.

    Returns (user_id, is_consultant). Raises 403 if not a consultant.
    """
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()

    # Check if user has Consultoria plan
    profile = await sb_execute(
        sb.table("profiles")
        .select("plan_type")
        .eq("id", user_id)
        .single()
    )

    if not profile.data:
        raise HTTPException(status_code=403, detail="Usuário não encontrado.")

    plan_type = profile.data.get("plan_type", "")
    is_consultant = "consultoria" in plan_type.lower()

    if not is_consultant:
        raise HTTPException(
            status_code=403,
            detail="Acesso restrito a assinantes do plano Consultoria.",
        )

    return user_id, True


async def _check_active_seats_limit(consultant_id: str) -> int:
    """Check active client count and verify it's under MAX_CLIENT_SEATS."""
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    resp = await sb_execute(
        sb.table("consultant_clients")
        .select("id", count="exact")
        .eq("consultant_id", consultant_id)
        .eq("status", "active")
    )

    active_count = resp.count or 0

    if active_count >= MAX_CLIENT_SEATS:
        raise HTTPException(
            status_code=400,
            detail=f"Limite de {MAX_CLIENT_SEATS} clientes ativos atingido. "
                   f"Faça upgrade para adicionar mais assentos.",
        )

    return active_count


# ---------------------------------------------------------------------------
# POST /consultoria/invite-client — Generate invite link for a client
# ---------------------------------------------------------------------------


@router.post(
    "/consultoria/invite-client",
    summary="Generate invite link for a client (CONSULT-001)",
    response_model=ConsultantInviteResponse,
)
async def invite_client(
    request: Request,
    body: InviteClientRequest,
    user_id: str = Depends(require_auth),
):
    if not get_feature_flag("CONSULTANT_SEATS_ENABLED", True):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")

    await _verify_consultant_access(user_id)
    await _check_active_seats_limit(user_id)

    # Generate invite token
    invite_token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=INVITE_LINK_EXPIRY_DAYS)).isoformat()

    base_url = os.getenv("FRONTEND_URL", "https://smartlic.tech")
    invite_url = f"{base_url}/consultoria/convite?token={invite_token}&consultor={user_id}"

    # Store invite (in-memory for now; use Redis in production)
    _invite_store[invite_token] = {
        "consultant_id": user_id,
        "client_email": body.client_email,
        "expires_at": expires_at,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(
        "Consultant %s invited client %s (expires %s)",
        user_id[:8], body.client_email, expires_at,
    )

    return ConsultantInviteResponse(
        invite_url=invite_url,
        expires_at=expires_at,
    )


# ---------------------------------------------------------------------------
# GET /consultoria/clients — List all clients for the consultant
# ---------------------------------------------------------------------------


@router.get(
    "/consultoria/clients",
    summary="List consultant's clients (CONSULT-001)",
    response_model=ConsultantClientListResponse,
)
async def list_clients(
    request: Request,
    status_filter: Optional[str] = Query(default=None, description="Filter by status: active, revoked"),
    user_id: str = Depends(require_auth),
):
    if not get_feature_flag("CONSULTANT_SEATS_ENABLED", True):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")

    await _verify_consultant_access(user_id)

    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    query = (
        sb.table("consultant_clients")
        .select("*, profiles!consultant_clients_client_id_fkey(email, full_name)")
        .eq("consultant_id", user_id)
        .order("created_at", desc=True)
    )

    if status_filter:
        if status_filter not in ("active", "revoked"):
            raise HTTPException(status_code=400, detail="Status inválido. Use 'active' ou 'revoked'.")
        query = query.eq("status", status_filter)

    resp = await sb_execute(query)
    rows = resp.data or []

    clients = []
    active_count = 0
    for row in rows:
        client_profile = row.get("profiles") or {}
        is_active = row.get("status") == "active"
        if is_active:
            active_count += 1
        clients.append(ConsultantClientResponse(
            id=row["id"],
            consultant_id=row["consultant_id"],
            client_id=row.get("client_id"),
            client_email=client_profile.get("email"),
            status=row["status"],
            created_at=row["created_at"],
        ))

    return ConsultantClientListResponse(
        clients=clients,
        total=len(clients),
        active_count=active_count,
    )


# ---------------------------------------------------------------------------
# DELETE /consultoria/clients/{client_id} — Revoke a client's access
# ---------------------------------------------------------------------------


@router.delete(
    "/consultoria/clients/{client_id}",
    summary="Revoke client access (CONSULT-001)",
)
async def revoke_client(
    request: Request,
    client_id: str,
    user_id: str = Depends(require_auth),
):
    if not get_feature_flag("CONSULTANT_SEATS_ENABLED", True):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")

    await _verify_consultant_access(user_id)

    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()

    # Find the relationship
    resp = await sb_execute(
        sb.table("consultant_clients")
        .select("id, status")
        .eq("consultant_id", user_id)
        .eq("client_id", client_id)
        .single()
    )

    if not resp.data:
        raise HTTPException(status_code=404, detail="Relação consultor-cliente não encontrada.")

    if resp.data.get("status") == "revoked":
        raise HTTPException(status_code=400, detail="Acesso já foi revogado.")

    # Update to revoked
    await sb_execute(
        sb.table("consultant_clients")
        .update({"status": "revoked"})
        .eq("id", resp.data["id"])
    )

    logger.info("Consultant %s revoked access for client %s", user_id[:8], client_id[:8])

    return {"message": "Acesso revogado com sucesso.", "client_id": client_id}


# ---------------------------------------------------------------------------
# POST /consultoria/share/{client_id} — Share a resource with a client
# ---------------------------------------------------------------------------


@router.post(
    "/consultoria/share/{client_id}",
    summary="Share a resource with a client (CONSULT-001)",
    response_model=ConsultantShareResponse,
)
async def share_resource(
    request: Request,
    client_id: str,
    body: ConsultantShareCreate,
    user_id: str = Depends(require_auth),
):
    if not get_feature_flag("CONSULTANT_SEATS_ENABLED", True):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")

    await _verify_consultant_access(user_id)

    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()

    # Verify client relationship exists and is active
    rel_resp = await sb_execute(
        sb.table("consultant_clients")
        .select("id, status")
        .eq("consultant_id", user_id)
        .eq("client_id", client_id)
        .single()
    )

    if not rel_resp.data:
        raise HTTPException(status_code=404, detail="Relação consultor-cliente não encontrada.")

    if rel_resp.data.get("status") != "active":
        raise HTTPException(status_code=400, detail="Cliente não está ativo. Reative o acesso primeiro.")

    # Create the share
    share_resp = await sb_execute(
        sb.table("consultant_shares")
        .insert({
            "consultant_id": user_id,
            "client_id": client_id,
            "resource_type": body.resource_type,
            "resource_id": body.resource_id,
        })
        .execute()
    )

    if not share_resp.data or len(share_resp.data) == 0:
        raise HTTPException(status_code=500, detail="Falha ao compartilhar recurso.")

    share = share_resp.data[0]

    logger.info(
        "Consultant %s shared %s/%s with client %s",
        user_id[:8], body.resource_type, body.resource_id[:8], client_id[:8],
    )

    return ConsultantShareResponse(
        id=share["id"],
        consultant_id=share["consultant_id"],
        client_id=share["client_id"],
        resource_type=share["resource_type"],
        resource_id=share["resource_id"],
        shared_at=share["shared_at"],
    )


# ---------------------------------------------------------------------------
# GET /consultoria/shared/{client_id} — Get shared resources for a client
# ---------------------------------------------------------------------------


@router.get(
    "/consultoria/shared/{client_id}",
    summary="List shared resources for a client (CONSULT-001)",
)
async def get_shared_resources(
    request: Request,
    client_id: str,
    resource_type: Optional[str] = Query(default=None, description="Filter by resource type"),
    user_id: str = Depends(require_auth),
):
    if not get_feature_flag("CONSULTANT_SEATS_ENABLED", True):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")

    await _verify_consultant_access(user_id)

    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    query = (
        sb.table("consultant_shares")
        .select("*")
        .eq("consultant_id", user_id)
        .eq("client_id", client_id)
        .order("shared_at", desc=True)
    )

    if resource_type:
        query = query.eq("resource_type", resource_type)

    resp = await sb_execute(query)
    rows = resp.data or []

    return {
        "client_id": client_id,
        "resources": [
            {
                "id": r["id"],
                "resource_type": r["resource_type"],
                "resource_id": r["resource_id"],
                "shared_at": r["shared_at"],
            }
            for r in rows
        ],
        "total": len(rows),
    }
