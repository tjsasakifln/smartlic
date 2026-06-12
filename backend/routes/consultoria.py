"""CONSULT-001: Consultant Seats routes."""

import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import require_auth
from config.features import get_feature_flag
from schemas.consultoria import (
    ConsultantClientResponse,
    ConsultantInviteResponse,
    ConsultantShareCreate,
    ConsultantShareResponse,
    InviteClientRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/consultoria", tags=["consultoria"])

MAX_CLIENT_SEATS = 10
INVITE_EXPIRY_DAYS = 7
CLIENT_INVITE_BASE_URL = "https://smartlic.tech/consultoria/convite"


def _get_user_plan(user: dict) -> str:
    return user.get("plan_type", "free_trial")


async def _require_consultant_plan(user: dict = Depends(require_auth)) -> dict:
    if not get_feature_flag("CONSULTANT_SEATS_ENABLED"):
        raise HTTPException(
            status_code=503,
            detail="Funcionalidade de assentos consultoria temporariamente indisponivel.",
        )
    plan = _get_user_plan(user)
    if plan != "consultoria":
        raise HTTPException(
            status_code=403,
            detail="Funcionalidade exclusiva do plano Consultoria (R$ 997/mes).",
        )
    return user


@router.post("/invite-client", response_model=ConsultantInviteResponse)
async def invite_client(
    body: InviteClientRequest,
    user: dict = Depends(_require_consultant_plan),
):
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        active_result = await sb_execute(
            sb.table("consultant_clients")
            .select("id", count="exact")
            .eq("consultant_id", user_id)
            .eq("status", "active")
        )
    except Exception:
        logger.exception("Failed to check active seat count")
        raise HTTPException(status_code=500, detail="Erro ao verificar limite de assentos.")

    active_count = getattr(active_result, "count", 0) or len(active_result.data or [])
    if active_count >= MAX_CLIENT_SEATS:
        raise HTTPException(
            status_code=403,
            detail=f"Limite de {MAX_CLIENT_SEATS} assentos ativos atingido.",
        )

    invite_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=INVITE_EXPIRY_DAYS)

    try:
        await sb_execute(
            sb.table("consultant_clients").insert({
                "consultant_id": user_id,
                "client_id": f"pending_{invite_token}",
                "status": "active",
            })
        )
    except Exception:
        logger.exception("Failed to create invite")
        raise HTTPException(status_code=500, detail="Erro ao criar convite.")

    invite_url = f"{CLIENT_INVITE_BASE_URL}/{invite_token}"
    logger.info("Consultant invite created: consultant=%s token_prefix=%s", user_id, invite_token[:8])

    return ConsultantInviteResponse(
        invite_url=invite_url,
        expires_at=expires_at.isoformat(),
    )


@router.get("/clients", response_model=list[ConsultantClientResponse])
async def list_clients(user: dict = Depends(_require_consultant_plan)):
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("consultant_clients")
            .select("id, consultant_id, client_id, status, created_at")
            .eq("consultant_id", user_id)
            .order("created_at", desc=True)
        )
    except Exception:
        logger.exception("Failed to list clients")
        raise HTTPException(status_code=500, detail="Erro ao listar clientes.")

    return [
        ConsultantClientResponse(
            id=row["id"],
            consultant_id=row["consultant_id"],
            client_id=row.get("client_id"),
            status=row.get("status", "active"),
            created_at=str(row.get("created_at", "")),
        )
        for row in (result.data or [])
    ]


@router.delete("/clients/{client_id}")
async def revoke_client(
    client_id: str,
    user: dict = Depends(_require_consultant_plan),
):
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        verify = await sb_execute(
            sb.table("consultant_clients")
            .select("id")
            .eq("id", client_id)
            .eq("consultant_id", user_id)
            .limit(1)
        )
    except Exception:
        logger.exception("Failed to verify client ownership")
        raise HTTPException(status_code=500, detail="Erro ao verificar cliente.")

    if not verify.data:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado.")

    try:
        await sb_execute(
            sb.table("consultant_clients")
            .update({"status": "revoked"})
            .eq("id", client_id)
            .eq("consultant_id", user_id)
        )
    except Exception:
        logger.exception("Failed to revoke client")
        raise HTTPException(status_code=500, detail="Erro ao revogar acesso do cliente.")

    try:
        await sb_execute(
            sb.table("consultant_shares")
            .delete()
            .eq("consultant_id", user_id)
            .eq("client_id", client_id)
        )
    except Exception:
        logger.warning("Failed to clean up shares for revoked client %s", client_id)

    logger.info("Client access revoked: consultant=%s client=%s", user_id, client_id)
    return {"status": "ok", "message": "Acesso do cliente revogado com sucesso."}


@router.post("/share/{client_id}", response_model=list[ConsultantShareResponse])
async def share_with_client(
    client_id: str,
    body: ConsultantShareCreate,
    user: dict = Depends(_require_consultant_plan),
):
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        verify = await sb_execute(
            sb.table("consultant_clients")
            .select("id")
            .eq("id", client_id)
            .eq("consultant_id", user_id)
            .eq("status", "active")
            .limit(1)
        )
    except Exception:
        logger.exception("Failed to verify client relationship")
        raise HTTPException(status_code=500, detail="Erro ao verificar cliente.")

    if not verify.data:
        raise HTTPException(status_code=404, detail="Cliente nao encontrado ou vinculo inativo.")

    try:
        result = await sb_execute(
            sb.table("consultant_shares").insert({
                "consultant_id": user_id,
                "client_id": client_id,
                "resource_type": body.resource_type,
                "resource_id": body.resource_id,
            })
        )
    except Exception:
        logger.exception("Failed to share resource")
        raise HTTPException(status_code=500, detail="Erro ao compartilhar recurso.")

    return [
        ConsultantShareResponse(
            id=row["id"],
            consultant_id=row["consultant_id"],
            client_id=row["client_id"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            shared_at=str(row.get("shared_at", "")),
        )
        for row in (result.data or [])
    ]


@router.get("/shared/{client_id}", response_model=list[ConsultantShareResponse])
async def list_shared_resources(
    client_id: str,
    user: dict = Depends(require_auth),
):
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    query = (
        sb.table("consultant_shares")
        .select("id, consultant_id, client_id, resource_type, resource_id, shared_at")
    )

    try:
        is_consultant = await sb_execute(
            sb.table("consultant_clients")
            .select("id")
            .eq("consultant_id", user_id)
            .eq("id", client_id)
            .limit(1)
        )
        if is_consultant.data:
            query = query.eq("consultant_id", user_id).eq("client_id", client_id)
        else:
            query = query.eq("client_id", user_id)
    except Exception:
        query = query.eq("client_id", user_id)

    try:
        result = await sb_execute(query.order("shared_at", desc=True))
    except Exception:
        logger.exception("Failed to list shared resources")
        raise HTTPException(status_code=500, detail="Erro ao listar recursos compartilhados.")

    return [
        ConsultantShareResponse(
            id=row["id"],
            consultant_id=row["consultant_id"],
            client_id=row["client_id"],
            resource_type=row["resource_type"],
            resource_id=row["resource_id"],
            shared_at=str(row.get("shared_at", "")),
        )
        for row in (result.data or [])
    ]
