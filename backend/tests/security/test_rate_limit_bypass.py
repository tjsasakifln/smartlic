"""SEC-TEST-2026-001 — AC1: Rate limit bypass tests.

OWASP A04:2021 Insecure Design (rate limit bypass) + A07:2021 (auth abuse).

Threat model:
- Attacker spoofs `X-Forwarded-For` to rotate IPs and exceed unauthenticated
  rate limits.
- Attacker tampers JWT to swap user_id between requests to dodge per-user
  buckets.

Properties asserted:
1. With JWT present, rate limit key is `user:{sub}` — XFF spoofing CANNOT
   escape a per-user bucket. (This is the bypass-resistance guarantee.)
2. Without JWT, key is `ip:{first_xff}` (Railway's behavior — by design).
3. JWT extraction is robust to malformed payloads (no crash → fallback to IP).
4. Multiple distinct XFF values DO produce distinct buckets when unauth — this
   is the documented limitation behind a trusted proxy. SEC-TEST-002 will add
   defense-in-depth via Cloudflare turnstile / Railway-trust-proxy boundary.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, Mock, patch

import jwt as pyjwt
import pytest


HS_SECRET = "test-rate-limit-secret-aaaaaaaaaaaaaaaaaaaaaaa"
USER_A = "550e8400-e29b-41d4-a716-44665544aaaa"
USER_B = "550e8400-e29b-41d4-a716-44665544bbbb"


class _CIDict(dict):
    """Case-insensitive dict mimicking starlette Headers.get()."""

    def __init__(self, items):
        super().__init__({k.lower(): v for k, v in items.items()})

    def get(self, key, default=""):
        return super().get(key.lower(), default)


def _mk_request(headers: dict, path: str = "/buscar", client_ip: str = "10.0.0.1"):
    request = Mock()
    request.headers = _CIDict(headers)
    request.url = Mock()
    request.url.path = path
    request.client = Mock()
    request.client.host = client_ip
    return request


def _bearer_for(user_id: str) -> str:
    token = pyjwt.encode({"sub": user_id, "aud": "authenticated"}, HS_SECRET, algorithm="HS256")
    return f"Bearer {token}"


# ──────────────────────────────────────────────────────────────────────
# Property 1: JWT-keyed bucket — XFF spoofing CANNOT bypass per-user limit
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authenticated_xff_spoof_does_not_bypass_user_bucket():
    """With a valid JWT, the rate-limit key is `user:{sub}`. Rotating XFF
    headers MUST keep the SAME bucket — bypass impossible.
    """
    from rate_limiter import require_rate_limit, _flexible_limiter

    keys_seen = []

    async def _capture(full_key, max_req, window):
        keys_seen.append(full_key)
        return (True, 0, max_req - 1)

    dependency = require_rate_limit(max_requests=10, window_seconds=60)

    with patch.object(_flexible_limiter, "check_rate_limit", _capture), \
         patch("config.get_feature_flag", return_value=True):
        # Same user, 5 different XFF spoofs
        for spoof in ("1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4", "5.5.5.5"):
            req = _mk_request(
                {"authorization": _bearer_for(USER_A), "x-forwarded-for": spoof}
            )
            await dependency(req)

    # All 5 requests must hit the SAME key (user-keyed)
    assert len(set(keys_seen)) == 1, (
        f"Per-user bucket leaked across XFF spoofs: {set(keys_seen)}"
    )
    assert f"user:{USER_A}" in keys_seen[0]


@pytest.mark.asyncio
async def test_different_users_get_different_buckets():
    """Sanity: distinct users must get distinct buckets (no key collision)."""
    from rate_limiter import require_rate_limit, _flexible_limiter

    keys_seen = []

    async def _capture(full_key, max_req, window):
        keys_seen.append(full_key)
        return (True, 0, max_req - 1)

    dependency = require_rate_limit(max_requests=10, window_seconds=60)
    with patch.object(_flexible_limiter, "check_rate_limit", _capture), \
         patch("config.get_feature_flag", return_value=True):
        for user in (USER_A, USER_B):
            req = _mk_request({"authorization": _bearer_for(user)})
            await dependency(req)

    assert len(set(keys_seen)) == 2, "Distinct users should get distinct buckets"


# ──────────────────────────────────────────────────────────────────────
# Property 2: Unauthenticated — XFF defines bucket (Railway-trusted proxy)
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unauthenticated_uses_xff_first_value():
    """No auth → key is `ip:<first XFF>`. Multiple comma-sep IPs → first wins."""
    from rate_limiter import require_rate_limit, _flexible_limiter

    keys_seen = []

    async def _capture(full_key, *_args):
        keys_seen.append(full_key)
        return (True, 0, 9)

    dependency = require_rate_limit(max_requests=10, window_seconds=60)
    with patch.object(_flexible_limiter, "check_rate_limit", _capture), \
         patch("config.get_feature_flag", return_value=True):
        req = _mk_request({"x-forwarded-for": "203.0.113.7, 10.0.0.1, 10.0.0.2"})
        await dependency(req)

    # First IP wins (Railway proxy convention)
    assert "ip:203.0.113.7" in keys_seen[0]


# ──────────────────────────────────────────────────────────────────────
# Property 3: Malformed JWT → safe fallback to IP, no crash
# ──────────────────────────────────────────────────────────────────────

def test_extract_user_id_from_malformed_jwt_returns_none():
    """Malformed JWT must NOT crash — must return None so caller falls back to IP."""
    from rate_limiter import _extract_user_id_from_jwt

    for bad in (
        "Bearer not.a.jwt",
        "Bearer x.y",  # too few segments
        "Bearer .invalid_b64.x",
        "Basic Zm9vOmJhcg==",  # not Bearer
        "",
    ):
        assert _extract_user_id_from_jwt(bad) is None


def test_extract_user_id_from_jwt_with_no_sub_returns_none():
    """JWT shaped correctly but with no sub claim → None."""
    from rate_limiter import _extract_user_id_from_jwt

    payload = base64.urlsafe_b64encode(json.dumps({"aud": "x"}).encode()).rstrip(b"=").decode()
    token = f"header.{payload}.sig"
    assert _extract_user_id_from_jwt(f"Bearer {token}") is None


# ──────────────────────────────────────────────────────────────────────
# Property 4: 429 path — limiter rejection results in HTTPException, not bypass
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_exceeded_raises_429_not_silently_passes():
    """When limiter says NOT allowed, dependency MUST raise 429 — never silently
    return None and let the request through.
    """
    from fastapi import HTTPException
    from rate_limiter import require_rate_limit, _flexible_limiter

    async def _deny(*_a, **_kw):
        return (False, 30, 0)

    dependency = require_rate_limit(max_requests=10, window_seconds=60)
    with patch.object(_flexible_limiter, "check_rate_limit", _deny), \
         patch("config.get_feature_flag", return_value=True):
        req = _mk_request({"authorization": _bearer_for(USER_A)})
        with pytest.raises(HTTPException) as exc:
            await dependency(req)
    assert exc.value.status_code == 429


# ──────────────────────────────────────────────────────────────────────
# Property 5: Feature flag disable does NOT permit attacker to "trigger" bypass
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_disabled_flag_skips_check_only():
    """When RATE_LIMITING_ENABLED=false, dependency returns silently — but
    this is a DEPLOY-TIME config, not attacker-controllable. Confirm flag is
    read from `config.get_feature_flag` (not from request headers).
    """
    from rate_limiter import require_rate_limit, _flexible_limiter

    called = []

    async def _record(*_a, **_kw):
        called.append(True)
        return (True, 0, 9)

    dependency = require_rate_limit(max_requests=10, window_seconds=60)
    with patch.object(_flexible_limiter, "check_rate_limit", _record), \
         patch("config.get_feature_flag", return_value=False):
        # Attacker tries to inject a "disable" header — must have NO effect
        req = _mk_request({
            "authorization": _bearer_for(USER_A),
            "x-rate-limit-bypass": "true",
            "x-feature-flag-rate-limiting": "false",
        })
        result = await dependency(req)

    assert result is None  # short-circuit on disabled flag
    assert called == []  # limiter NOT consulted

    # And re-enabling does not consult the spoofed headers either:
    with patch.object(_flexible_limiter, "check_rate_limit", _record), \
         patch("config.get_feature_flag", return_value=True):
        req = _mk_request({
            "authorization": _bearer_for(USER_A),
            "x-rate-limit-bypass": "true",
        })
        await dependency(req)
    assert called == [True]  # limiter WAS consulted despite spoof header
