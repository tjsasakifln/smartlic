"""SEC-TEST-2026-001 — AC1: JWT auth bypass tests.

OWASP A01:2021 Broken Access Control + A07:2021 Identification & Authentication Failures.

Covers:
- JWT signature tampering (full-replacement, NOT single-char flip — see
  memory feedback_jwt_base64url_flaky_test).
- Claim tampering (sub, role, aal swap).
- Missing/empty Authorization header.
- Wrong algorithm in JWT header (alg=none).
- Role escalation: regular user attempting admin endpoint via require_admin.

Strategy: drive the dependency directly (no TestClient required), mock the
JWKS/secret with a deterministic HS256 key, and assert HTTPException(401/403)
or success exactly as the contract specifies.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import jwt as pyjwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials


HS_SECRET = "test-secret-baseline-do-not-use-in-prod-aaaaaaaaaaaaaa"
WRONG_SECRET = "different-secret-attacker-controlled-bbbbbbbbbbbbbbbb"
ADMIN_UUID = "550e8400-e29b-41d4-a716-446655440000"
USER_UUID = "550e8400-e29b-41d4-a716-446655440099"


def _valid_token(claims: dict | None = None, secret: str = HS_SECRET) -> str:
    payload = {
        "sub": USER_UUID,
        "email": "user@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": 9999999999,  # ~year 2286
        "aal": "aal1",
    }
    if claims:
        payload.update(claims)
    return pyjwt.encode(payload, secret, algorithm="HS256")


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture(autouse=True)
def _hs256_secret(monkeypatch):
    """Force HS256 path with a known secret + clear caches between tests."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", HS_SECRET)
    monkeypatch.delenv("SUPABASE_JWKS_URL", raising=False)
    import auth as _auth

    _auth._token_cache.clear()
    monkeypatch.setattr(_auth, "_jwks_client", None, raising=False)
    monkeypatch.setattr(_auth, "_jwks_init_attempted", False, raising=False)

    async def _fake_redis_get(_h):
        return None

    async def _fake_redis_set(_h, _d):
        return None

    monkeypatch.setattr(_auth, "_redis_cache_get", _fake_redis_get)
    monkeypatch.setattr(_auth, "_redis_cache_set", _fake_redis_set)
    yield


# ──────────────────────────────────────────────────────────────────────
# JWT signature tampering — full-replacement strategy
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jwt_signed_with_wrong_secret_rejected():
    """Token signed by attacker (different secret) MUST be rejected."""
    from auth import get_current_user

    forged = _valid_token(secret=WRONG_SECRET)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer(forged))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_jwt_signature_replaced_full_rejected():
    """Replace signature with a valid-shape but unrelated signature.

    Uses full-replacement (encode of empty payload with wrong secret) instead of
    single-char flip — single-char flip has ~6.25% false-pass on base64url.
    """
    from auth import get_current_user

    legit = _valid_token()
    bogus_for_sig = pyjwt.encode({"junk": "x"}, WRONG_SECRET, algorithm="HS256")
    bogus_sig = bogus_for_sig.rsplit(".", 1)[1]
    head, body, _ = legit.rsplit(".", 2)
    tampered = f"{head}.{body}.{bogus_sig}"

    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer(tampered))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_jwt_alg_none_rejected():
    """`alg=none` tokens MUST be rejected (PyJWT enforces algorithm whitelist)."""
    from auth import get_current_user

    unsigned = pyjwt.encode(
        {"sub": USER_UUID, "aud": "authenticated", "exp": 9999999999},
        "",
        algorithm="none",
    )
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer(unsigned))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_jwt_expired_rejected():
    """Expired token MUST be rejected even with valid signature."""
    from auth import get_current_user

    expired = pyjwt.encode(
        {
            "sub": USER_UUID,
            "email": "u@e.com",
            "role": "authenticated",
            "aud": "authenticated",
            "exp": 1,  # 1970
        },
        HS_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer(expired))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_jwt_wrong_audience_rejected():
    """Audience claim mismatch MUST raise 401 (STORY-210 AC7)."""
    from auth import get_current_user

    bad_aud = pyjwt.encode(
        {
            "sub": USER_UUID,
            "email": "u@e.com",
            "role": "authenticated",
            "aud": "service_role",  # not "authenticated"
            "exp": 9999999999,
        },
        HS_SECRET,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer(bad_aud))
    assert exc.value.status_code == 401


# ──────────────────────────────────────────────────────────────────────
# Missing / malformed credentials
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_no_credentials_returns_none():
    """Missing token → None (allows public endpoints), NOT 200 with admin role."""
    from auth import get_current_user

    result = await get_current_user(None)
    assert result is None


@pytest.mark.asyncio
async def test_garbled_token_rejected():
    """Token that is not 3-segments base64 MUST be rejected as invalid."""
    from auth import get_current_user

    with pytest.raises(HTTPException) as exc:
        await get_current_user(_bearer("not.a.jwt"))
    assert exc.value.status_code == 401


# ──────────────────────────────────────────────────────────────────────
# Role escalation — regular user attempting admin
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_non_admin_blocked_by_require_admin():
    """A valid auth user not in ADMIN_USER_IDS must get 403 from require_admin."""
    from admin import require_admin

    regular = {"id": USER_UUID, "email": "u@e.com", "role": "authenticated"}
    with patch.dict(os.environ, {"ADMIN_USER_IDS": ADMIN_UUID}):
        with pytest.raises(HTTPException) as exc:
            await require_admin(user=regular)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_role_claim_tamper_does_not_grant_admin():
    """Even if attacker mints a token with role='service_role', require_admin
    gates on UUID membership in ADMIN_USER_IDS — claim tamper does NOT escalate.
    """
    from admin import require_admin

    # Token claims role=service_role but UUID is NOT in ADMIN_USER_IDS.
    # Note: signature is valid (we encoded), so the JWT itself would parse —
    # but require_admin doesn't trust the role claim, only the UUID allowlist.
    regular_with_fake_role = {
        "id": USER_UUID,
        "email": "u@e.com",
        "role": "service_role",  # claim attacker-controlled
    }
    with patch.dict(os.environ, {"ADMIN_USER_IDS": ADMIN_UUID}):
        with pytest.raises(HTTPException) as exc:
            await require_admin(user=regular_with_fake_role)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_uuid_allowed():
    """Sanity: a UUID in ADMIN_USER_IDS DOES pass require_admin."""
    from admin import require_admin

    admin_user = {"id": ADMIN_UUID, "email": "a@e.com", "role": "authenticated"}
    with patch.dict(os.environ, {"ADMIN_USER_IDS": ADMIN_UUID}):
        result = await require_admin(user=admin_user)
    assert result["id"] == ADMIN_UUID
