"""#1811: Admin session revocation with JWT blacklist.

POST /v1/admin/users/{user_id}/revoke-sessions — revoga sessoes de um usuario (admin)
POST /v1/admin/revoke-all-sessions — revoga TODAS as sessoes (master only)

Redis keys:
  session_revoke:{user_id}  — SET with 24h TTL (individual revocation)
  global_revoke_ts           — SET with current timestamp (global revocation)

Fail-open: Redis unavailable → revocation flag NOT set → 503 to caller.
Graceful degradation: Redis down → session checks in auth.py skip silently.

RBAC Phase 2 (#1954): user session revocation requires ``admin:ops`` role.
Global revocation additionally requires master access.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from auth import require_auth
from rbac_granular import require_admin_ops
from authorization import has_master_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])

# ---------------------------------------------------------------------------
# Redis key constants
# ---------------------------------------------------------------------------
_REVOKE_KEY_PREFIX = "session_revoke:"
_GLOBAL_REVOKE_KEY = "global_revoke_ts"
_REVOKE_TTL = 86400  # 24h — covers max JWT lifetime


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class RevokeSessionsResponse(BaseModel):
    status: str = Field(description="ok | skipped")
    user_id: str
    detail: str


class RevokeAllSessionsRequest(BaseModel):
    reason: str = Field(
        default="",
        description="Motivo da revogacao em massa (para auditoria)",
        examples=["Incidente de seguranca — token vazado"],
    )


class RevokeAllSessionsResponse(BaseModel):
    status: str = Field(description="ok")
    revoked_at: str = Field(description="ISO timestamp da revogacao global")
    reason: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _get_redis():
    """Return Redis connection or None."""
    try:
        from redis_pool import get_redis_pool

        return await get_redis_pool()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# POST /v1/admin/users/{user_id}/revoke-sessions
# ---------------------------------------------------------------------------
@router.post("/users/{user_id}/revoke-sessions", response_model=RevokeSessionsResponse)
async def revoke_user_sessions(
    user_id: str,
    request: Request,
    user: dict = Depends(require_auth),
):
    """Revoke all sessions for a specific user.

    Admin-only. Sets a Redis blacklist key with 24h TTL.
    Auth middleware checks this key on every request.
    """
    await require_admin_ops(user=user)

    admin_id = user["id"]

    redis = await _get_redis()
    if not redis:
        logger.error(
            f"Session revocation FAILED for {user_id[:8]}*** — Redis unavailable "
            f"(admin={admin_id[:8]}***)"
        )
        raise HTTPException(
            status_code=503,
            detail="Redis unavailable — cannot revoke sessions at this time",
        )

    key = f"{_REVOKE_KEY_PREFIX}{user_id}"
    await redis.setex(key, _REVOKE_TTL, str(int(time.time())))

    logger.warning(
        f"ADMIN SESSION REVOKE — admin={admin_id[:8]}*** "
        f"revoked={user_id[:8]}*** ttl={_REVOKE_TTL}s"
    )

    return RevokeSessionsResponse(
        status="ok",
        user_id=user_id,
        detail=f"Sessions revoked. Blacklist active for {_REVOKE_TTL}s.",
    )


# ---------------------------------------------------------------------------
# POST /v1/admin/revoke-all-sessions
# ---------------------------------------------------------------------------
@router.post("/revoke-all-sessions", response_model=RevokeAllSessionsResponse)
async def revoke_all_sessions(
    request: Request,
    body: RevokeAllSessionsRequest = RevokeAllSessionsRequest(),
    user: dict = Depends(require_auth),
):
    """Revoke ALL active sessions globally. Master-only.

    Sets a global timestamp in Redis. All tokens issued before this
    timestamp are invalidated in the auth middleware.
    """
    await require_admin_ops(user=user)
    if not await has_master_access(user["id"]):
        raise HTTPException(status_code=403, detail="Apenas master pode revogar todas as sessoes")

    admin_id = user["id"]
    now_ts = int(time.time())
    reason = body.reason or "Revogacao em massa iniciada pelo master"

    redis = await _get_redis()
    if not redis:
        logger.error(
            f"Global revocation FAILED — Redis unavailable (master={admin_id[:8]}***)"
        )
        raise HTTPException(
            status_code=503,
            detail="Redis unavailable — cannot perform global revocation",
        )

    await redis.set(_GLOBAL_REVOKE_KEY, str(now_ts))

    # Invalidate all L2 auth caches so cached tokens hit the slow path
    # where global_revoke_ts is checked against JWT iat
    try:
        keys = await redis.keys("smartlic:auth:*")
        if keys:
            await redis.delete(*keys)
            logger.warning(f"Cleared {len(keys)} L2 auth cache entries for global revocation")
    except Exception:
        pass

    logger.warning(
        f"GLOBAL SESSION REVOCATION — master={admin_id[:8]}*** "
        f"reason={reason} ts={now_ts}"
    )

    from datetime import datetime, timezone

    revoked_at = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()

    return RevokeAllSessionsResponse(
        status="ok",
        revoked_at=revoked_at,
        reason=reason,
    )
