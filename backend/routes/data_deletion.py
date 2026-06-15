"""#1804: LGPD data deletion flow (Art. 18 — direito à exclusão).

POST /v1/me/request-deletion  — solicita exclusão (envia email de confirmação)
POST /v1/me/confirm-deletion   — confirma com token do email (double opt-out)
POST /v1/me/cancel-deletion    — cancela solicitação pendente
DELETE /v1/me/admin/{user_id}  — admin força exclusão direta (bypass double opt-out)

Soft-delete via profiles.deleted_at + anonimização de PII.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth import require_auth
from authorization import is_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/me", tags=["data-deletion"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_DELETION_TOKEN_TTL = 86400  # 24h para confirmar
_DELETION_SECRET = "smartlic-lgpd-deletion-v1"  # pepper for HMAC


def _make_deletion_hash(raw_token: str) -> str:
    """HMAC-SHA256 do token (pepper + raw token)."""
    return hmac.new(
        _DELETION_SECRET.encode(),
        raw_token.encode(),
        hashlib.sha256,
    ).hexdigest()


def _verify_deletion_hash(raw_token: str, stored_hash: str) -> bool:
    """Constant-time comparison do token HMAC."""
    expected = _make_deletion_hash(raw_token)
    return hmac.compare_digest(expected, stored_hash)


def _anonymize_profile_data(profile: dict) -> dict:
    """Anonymize PII fields for LGPD soft-delete."""
    import hashlib

    uid_hash = hashlib.sha256(profile.get("id", "0").encode()).hexdigest()[:8]
    return {
        "email": f"deleted_{uid_hash}@anonymous",
        "nome": "Usuario Excluido",
        "phone": "",
        "cpf_cnpj": None,
        "cnae_primario": None,
        "uf_list": [],
        "deleted_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class DeletionRequestResponse(BaseModel):
    status: str
    detail: str


class ConfirmDeletionRequest(BaseModel):
    token: str = Field(..., description="Raw token do email de confirmação")


class CancelDeletionResponse(BaseModel):
    status: str
    detail: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_sb():
    from supabase_client import get_supabase

    return get_supabase()


async def _sb_execute(query):
    from supabase_client import sb_execute

    return await sb_execute(query)


# ---------------------------------------------------------------------------
# POST /v1/me/request-deletion
# ---------------------------------------------------------------------------
@router.post("/request-deletion", response_model=DeletionRequestResponse)
async def request_deletion(request: Request, user: dict = Depends(require_auth)):
    """Solicita exclusão de dados. Envia email de confirmação (double opt-out).

    Idempotente: se já existe pending, retorna 200 sem criar novo token.
    """
    user_id = user["id"]
    sb = await _get_sb()

    # Verifica se já tem pending
    existing = await _sb_execute(
        sb.table("data_deletion_requests")
        .select("id, status")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .limit(1)
    )
    if existing.data:
        return DeletionRequestResponse(
            status="already_pending",
            detail="Solicitação de exclusão já existe. Verifique seu email.",
        )

    # Gera token seguro
    raw_token = secrets.token_urlsafe(32)
    token_hash = _make_deletion_hash(raw_token)

    # Insere na tabela
    await _sb_execute(
        sb.table("data_deletion_requests").insert({
            "user_id": user_id,
            "status": "pending",
            "deletion_token": token_hash,
            "reason": "",
        })
    )

    # Envia email de confirmação
    try:
        from email_service import send_email

        confirm_url = f"https://smartlic.tech/conta/excluir?token={raw_token}"
        send_email(
            to=user.get("email", ""),
            subject="Confirme a exclusão da sua conta SmartLic",
            html=f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="UTF-8"></head>
<body style="font-family: sans-serif; padding: 40px;">
  <h2>Confirmação de exclusão de conta</h2>
  <p>Você solicitou a exclusão da sua conta SmartLic.</p>
  <p>Clique no botão abaixo para confirmar:</p>
  <a href="{confirm_url}"
     style="display:inline-block;padding:12px 24px;background:#dc2626;color:#fff;
            text-decoration:none;border-radius:6px;font-weight:bold;">
    Excluir minha conta
  </a>
  <p style="margin-top:20px;color:#666;font-size:14px;">
    Este link expira em 24 horas. Se você não solicitou esta exclusão, ignore este email.
  </p>
</body>
</html>""",
            tags=[{"name": "category", "value": "lgpd"}, {"name": "type", "value": "deletion"}],
        )
    except Exception as e:
        logger.error(f"Failed to send deletion confirmation email: {e}")

    logger.warning(f"LGPD deletion requested: user={user_id[:8]}***")
    return DeletionRequestResponse(
        status="pending",
        detail="Email de confirmação enviado. Verifique sua caixa de entrada.",
    )


# ---------------------------------------------------------------------------
# POST /v1/me/confirm-deletion
# ---------------------------------------------------------------------------
@router.post("/confirm-deletion", response_model=DeletionRequestResponse)
async def confirm_deletion(
    request: Request,
    body: ConfirmDeletionRequest,
    user: dict = Depends(require_auth),
):
    """Confirma exclusão com token do email. Anonimiza perfil (soft-delete)."""
    user_id = user["id"]
    sb = await _get_sb()

    # Busca pending request
    pending = await _sb_execute(
        sb.table("data_deletion_requests")
        .select("id, deletion_token, requested_at")
        .eq("user_id", user_id)
        .eq("status", "pending")
        .order("requested_at", desc=True)
        .limit(1)
    )

    if not pending.data:
        raise HTTPException(status_code=404, detail="Nenhuma solicitação de exclusão pendente")

    record = pending.data[0]

    # Verifica expiração (24h)
    requested_at = datetime.fromisoformat(record["requested_at"].replace("Z", "+00:00"))
    age_s = (datetime.now(timezone.utc) - requested_at).total_seconds()
    if age_s > _DELETION_TOKEN_TTL:
        # Cancela request expirado
        await _sb_execute(
            sb.table("data_deletion_requests")
            .update({"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", record["id"])
        )
        raise HTTPException(status_code=410, detail="Token expirado. Solicite nova exclusão.")

    # Verifica token (constant-time)
    if not _verify_deletion_hash(body.token, record["deletion_token"]):
        raise HTTPException(status_code=403, detail="Token inválido")

    # Anonimiza perfil (soft-delete)
    anon = _anonymize_profile_data({"id": user_id})
    await _sb_execute(
        sb.table("profiles")
        .update(anon)
        .eq("id", user_id)
    )

    # Marca request como completed
    now_iso = datetime.now(timezone.utc).isoformat()
    await _sb_execute(
        sb.table("data_deletion_requests")
        .update({
            "status": "completed",
            "confirmed_at": now_iso,
            "completed_at": now_iso,
        })
        .eq("id", record["id"])
    )

    logger.warning(f"LGPD deletion completed: user={user_id[:8]}***")
    return DeletionRequestResponse(
        status="completed",
        detail="Conta excluída. Seus dados foram anonimizados.",
    )


# ---------------------------------------------------------------------------
# POST /v1/me/cancel-deletion
# ---------------------------------------------------------------------------
@router.post("/cancel-deletion", response_model=CancelDeletionResponse)
async def cancel_deletion(request: Request, user: dict = Depends(require_auth)):
    """Cancela uma solicitação de exclusão pendente."""
    user_id = user["id"]
    sb = await _get_sb()

    await _sb_execute(
        sb.table("data_deletion_requests")
        .update({
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("user_id", user_id)
        .eq("status", "pending")
    )

    return CancelDeletionResponse(status="cancelled", detail="Solicitação de exclusão cancelada.")


# ---------------------------------------------------------------------------
# DELETE /v1/me/admin/{user_id} — Admin force-deletion
# ---------------------------------------------------------------------------
@router.delete("/admin/{user_id}", response_model=DeletionRequestResponse)
async def admin_delete_user(
    user_id: str,
    request: Request,
    user: dict = Depends(require_auth),
):
    """Admin força exclusão de um usuário (bypass double opt-out)."""
    if not await is_admin(user["id"]):
        raise HTTPException(status_code=403, detail="Apenas administradores")

    sb = await _get_sb()
    anon = _anonymize_profile_data({"id": user_id})

    await _sb_execute(sb.table("profiles").update(anon).eq("id", user_id))

    logger.warning(f"LGPD admin-force deletion: admin={user['id'][:8]}*** target={user_id[:8]}***")
    return DeletionRequestResponse(
        status="completed",
        detail=f"Usuário {user_id[:8]}*** excluído por admin.",
    )
