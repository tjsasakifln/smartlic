"""Workspace integration channels CRUD — B2GOPS-015 (#2025).

Reduced scope: CRUD for integration channels + test endpoint only.
No dispatcher, no retry, no complex templates.

Endpoints (all authenticated):
    GET    /canais              — List user's integration channels
    POST   /canais              — Create integration channel
    DELETE /canais/{id}         — Delete integration channel
    POST   /test/{id}           — Send test notification
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from auth import require_auth
from schemas.workspace_integracoes import (
    CanalIntegracao,
    CanalIntegracaoCreate,
    TestNotificacaoResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspace-integracoes"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_id(user: dict) -> str:
    return user.get("sub") or user.get("id", "")


def _row_to_canal(row: dict) -> CanalIntegracao:
    """Convert a Supabase row dict into a CanalIntegracao response."""
    return CanalIntegracao(
        id=row["id"],
        user_id=row["user_id"],
        tipo=row["tipo"],
        nome=row["nome"],
        url=row.get("url"),
        email_destino=row.get("email_destino"),
        eventos=row.get("eventos") or [],
        ativo=row.get("ativo", True),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _validate_create(body: CanalIntegracaoCreate) -> None:
    """Validate that required fields are present for the chosen channel type."""
    if body.tipo in ("slack", "teams"):
        if not body.url:
            raise HTTPException(
                status_code=422,
                detail=f"url é obrigatório para canal do tipo {body.tipo}",
            )
    elif body.tipo == "email":
        if not body.email_destino:
            raise HTTPException(
                status_code=422,
                detail="email_destino é obrigatório para canal do tipo email",
            )


async def _fetch_canal(canal_id: str, uid: str) -> dict:
    """Fetch a channel from DB and verify ownership.

    Returns the row dict, or raises HTTPException 404/403.
    """
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    result = await sb_execute(
        sb.table("workspace_integracao_canais")
        .select("*")
        .eq("id", canal_id)
        .limit(1)
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Canal não encontrado")

    row = result.data[0]
    if row.get("user_id") != uid:
        raise HTTPException(
            status_code=403,
            detail="Você não tem permissão para acessar este canal",
        )

    return row


# ---------------------------------------------------------------------------
# GET /canais — List user's integration channels
# ---------------------------------------------------------------------------


@router.get("/canais", response_model=list[CanalIntegracao])
async def list_canais(
    user: dict = Depends(require_auth),
):
    """List all integration channels for the authenticated user."""
    uid = _user_id(user)

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("workspace_integracao_canais")
            .select("*")
            .eq("user_id", uid)
            .order("created_at", desc=True)
        )
    except Exception as exc:
        logger.error("Failed to list channels for user %s: %s", uid[:8], exc)
        raise HTTPException(status_code=500, detail="Erro ao listar canais")

    return [_row_to_canal(r) for r in (result.data or [])]


# ---------------------------------------------------------------------------
# POST /canais — Create integration channel
# ---------------------------------------------------------------------------


@router.post("/canais", response_model=CanalIntegracao, status_code=201)
async def create_canal(
    body: CanalIntegracaoCreate,
    user: dict = Depends(require_auth),
):
    """Create a new integration channel (Slack, Teams, or Email)."""
    _validate_create(body)

    uid = _user_id(user)

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("workspace_integracao_canais")
            .insert({
                "user_id": uid,
                "tipo": body.tipo,
                "nome": body.nome,
                "url": body.url,
                "email_destino": body.email_destino,
                "eventos": body.eventos,
            })
            .select("*"),
            category="write",
        )
    except Exception as exc:
        logger.error("Failed to create channel for user %s: %s", uid[:8], exc)
        raise HTTPException(status_code=500, detail="Erro ao criar canal")

    row = result.data[0] if result.data else {}
    logger.info(
        "Channel created for user %s (tipo=%s, id=%s)",
        uid[:8], body.tipo, row.get("id", "")[:8],
    )
    return _row_to_canal(row)


# ---------------------------------------------------------------------------
# DELETE /canais/{canal_id} — Delete integration channel
# ---------------------------------------------------------------------------


@router.delete("/canais/{canal_id}", status_code=204, response_model=None)
async def delete_canal(
    canal_id: UUID,
    user: dict = Depends(require_auth),
):
    """Delete an integration channel."""
    uid = _user_id(user)

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()

        # Verify ownership
        check = await sb_execute(
            sb.table("workspace_integracao_canais")
            .select("id, user_id")
            .eq("id", str(canal_id))
            .limit(1)
        )
        if not check.data:
            raise HTTPException(status_code=404, detail="Canal não encontrado")

        row = check.data[0]
        if row.get("user_id") != uid:
            raise HTTPException(
                status_code=403,
                detail="Você não tem permissão para excluir este canal",
            )

        await sb_execute(
            sb.table("workspace_integracao_canais")
            .delete()
            .eq("id", str(canal_id))
            .eq("user_id", uid),
            category="write",
        )

        logger.info("Channel %s deleted by user %s", str(canal_id)[:8], uid[:8])

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to delete channel %s for user %s: %s",
            str(canal_id)[:8], uid[:8], exc,
        )
        raise HTTPException(status_code=500, detail="Erro ao excluir canal")


# ---------------------------------------------------------------------------
# POST /test/{canal_id} — Send test notification
# ---------------------------------------------------------------------------


@router.post("/test/{canal_id}", response_model=TestNotificacaoResponse)
async def test_canal(
    canal_id: UUID,
    user: dict = Depends(require_auth),
):
    """Send a test notification to verify the channel configuration.

    - Slack: POST to webhook URL with a plain text message
    - Teams: POST to webhook URL with a simple MessageCard
    - Email: send via Resend API
    """
    uid = _user_id(user)

    try:
        canal = await _fetch_canal(str(canal_id), uid)

        tipo = canal.get("tipo", "")
        sucesso = False

        if tipo == "slack":
            url = canal.get("url", "")
            if not url:
                raise HTTPException(status_code=422, detail="URL do webhook não configurada")

            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json={"text": "Teste de notificacao do SmartLic"},
                )
                resp.raise_for_status()
            sucesso = True

        elif tipo == "teams":
            url = canal.get("url", "")
            if not url:
                raise HTTPException(status_code=422, detail="URL do webhook não configurada")

            import httpx

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    json={
                        "@type": "MessageCard",
                        "@context": "https://schema.org/extensions",
                        "summary": "Teste SmartLic",
                        "title": "Teste de Notificacao SmartLic",
                        "sections": [
                            {
                                "text": (
                                    "Esta e uma notificacao de teste para "
                                    "verificar a configuracao do seu canal."
                                ),
                            }
                        ],
                    },
                )
                resp.raise_for_status()
            sucesso = True

        elif tipo == "email":
            email_destino = canal.get("email_destino", "")
            if not email_destino:
                raise HTTPException(status_code=422, detail="Email de destino não configurado")

            from email_service import send_email

            email_id = send_email(
                to=email_destino,
                subject="Teste de Notificacao SmartLic",
                html=(
                    "<h2>Teste de Notificacao SmartLic</h2>"
                    "<p>Esta e uma notificacao de teste para "
                    "verificar a configuracao do seu canal de email.</p>"
                ),
                tags=[{"name": "category", "value": "test"}],
            )
            sucesso = bool(email_id)

        else:
            raise HTTPException(status_code=400, detail=f"Tipo de canal desconhecido: {tipo}")

        if sucesso:
            logger.info(
                "Test notification sent via channel %s for user %s",
                str(canal_id)[:8], uid[:8],
            )
            return TestNotificacaoResponse(
                sucesso=True,
                mensagem="Notificação de teste enviada com sucesso",
            )

        return TestNotificacaoResponse(
            sucesso=False,
            mensagem="Falha ao enviar notificação de teste",
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to test channel %s for user %s: %s",
            str(canal_id)[:8], uid[:8], exc,
        )
        return TestNotificacaoResponse(
            sucesso=False,
            mensagem="Erro ao enviar notificação de teste",
        )
