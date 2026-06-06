"""API Keys CRUD — API-SELF-001 (#1418).

Endpoints:
    POST   /v1/api-keys        — create a new API key (plaintext returned ONCE)
    GET    /v1/api-keys        — list user's non-revoked keys
    DELETE /v1/api-keys/{id}   — revoke (soft-delete) an API key
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from auth import require_auth
from log_sanitizer import mask_api_key
from schemas.api_keys import ApiKeyCreate, ApiKeyCreated, ApiKeyResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

API_KEY_PREFIX = "sk_"


def _hash_key(plaintext: str) -> str:
    """SHA-256 hash of the plaintext key for storage.

    SHA-256 is appropriate here because API keys are high-entropy random
    tokens (256 bits), not low-entropy passwords. No salt needed because
    each key is already unique and unpredictable.
    """
    return hashlib.sha256(plaintext.encode()).hexdigest()


def _generate_key() -> tuple[str, str]:
    """Generate (plaintext, sha256_hash) pair."""
    raw = secrets.token_urlsafe(32)  # 43 base64url chars
    plaintext = f"{API_KEY_PREFIX}{raw}"
    key_hash = _hash_key(plaintext)
    return plaintext, key_hash


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# CRUD Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    body: ApiKeyCreate,
    user: dict = Depends(require_auth),
):
    """Create a new API key. The plaintext key is returned ONCE."""
    plaintext, key_hash = _generate_key()
    user_id = user.get("sub") or user.get("id", "")

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("api_keys")
            .insert({
                "user_id": user_id,
                "key_hash": key_hash,
                "name": body.name,
            })
            .select("id, name, created_at")
        )
    except Exception as exc:
        logger.error("Failed to create API key: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao criar chave de API")

    row = result.data[0] if result.data else {}
    logger.info(
        "API key created for user %s (name=%s, id=%s)",
        user_id[:8], row.get("name", ""), row.get("id", "")[:8],
    )
    # Log mask — never log plaintext
    logger.debug("API key plaintext (masked): %s", mask_api_key(plaintext))

    return ApiKeyCreated(
        id=row.get("id", ""),
        name=row.get("name", body.name),
        plaintext_key=plaintext,
        created_at=row.get("created_at", _now_iso()),
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(user: dict = Depends(require_auth)):
    """List all non-revoked API keys for the authenticated user."""
    user_id = user.get("sub") or user.get("id", "")

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()
        result = await sb_execute(
            sb.table("api_keys")
            .select("id, name, created_at, last_used_at")
            .eq("user_id", user_id)
            .is_("revoked_at", "null")
            .order("created_at", desc=True)
        )
    except Exception as exc:
        logger.error("Failed to list API keys: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao listar chaves de API")

    return [
        ApiKeyResponse(
            id=r["id"],
            name=r.get("name", ""),
            created_at=r.get("created_at", _now_iso()),
            last_used_at=r.get("last_used_at"),
        )
        for r in (result.data or [])
    ]


@router.delete("/{key_id}", status_code=204, response_model=None)
async def revoke_api_key(key_id: str, user: dict = Depends(require_auth)):
    """Revoke (soft-delete) an API key. Only the owner can revoke."""
    user_id = user.get("sub") or user.get("id", "")

    try:
        from supabase_client import get_supabase, sb_execute

        sb = get_supabase()

        # Verify ownership
        check = await sb_execute(
            sb.table("api_keys")
            .select("id, user_id")
            .eq("id", key_id)
            .limit(1)
        )
        if not check.data:
            raise HTTPException(status_code=404, detail="Chave de API não encontrada")

        row = check.data[0]
        if row.get("user_id") != user_id:
            raise HTTPException(
                status_code=403,
                detail="Você não tem permissão para revogar esta chave",
            )

        # Soft-delete by setting revoked_at
        await sb_execute(
            sb.table("api_keys")
            .update({"revoked_at": _now_iso()})
            .eq("id", key_id)
            .eq("user_id", user_id),
            category="write",
        )

        logger.info("API key %s revoked by user %s", key_id[:8], user_id[:8])

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to revoke API key %s: %s", key_id[:8], exc)
        raise HTTPException(status_code=500, detail="Erro ao revogar chave de API")
