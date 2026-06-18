"""#1924: Tests for admin session revocation endpoints.

Covers:
- POST /v1/admin/users/{user_id}/revoke-sessions
  — revoke all sessions for a user (admin)
- POST /v1/admin/revoke-all-sessions
  — revoke ALL sessions globally (master only)

Fix included: missing ``await require_admin(user)`` on both routes (the call
was a no-op before this fix).
"""

from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-not-used-for-override")
os.environ.setdefault("SUPABASE_URL", "http://localhost:8000")

from main import app  # noqa: E402
from auth import require_auth  # noqa: E402

# ---------------------------------------------------------------------------
# Constants matching admin_sessions.py
# ---------------------------------------------------------------------------
_REVOKE_KEY_PREFIX = "session_revoke:"
_GLOBAL_REVOKE_KEY = "global_revoke_ts"
_REVOKE_TTL = 86400

# Test user IDs
ADMIN_ID = "00000000-0000-0000-0000-00000000a001"
MASTER_ID = "00000000-0000-0000-0000-00000000a002"
REGULAR_USER_ID = "regular-user-id-for-non-admin"
TARGET_USER_ID = "00000000-0000-0000-0000-00000000b001"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client():
    """TestClient authenticated as an admin user."""
    fake_admin = {"id": ADMIN_ID, "email": "admin@test.com"}
    app.dependency_overrides[require_auth] = lambda: fake_admin
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def regular_client():
    """TestClient authenticated as a regular (non-admin) user."""
    fake_user = {"id": REGULAR_USER_ID, "email": "user@test.com"}
    app.dependency_overrides[require_auth] = lambda: fake_user
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture
def mock_redis():
    """AsyncMock that simulates a Redis connection."""
    redis = AsyncMock()
    redis.setex = AsyncMock()
    redis.set = AsyncMock()
    redis.keys = AsyncMock(return_value=[])
    redis.delete = AsyncMock()
    return redis


# ===========================================================================
# POST /v1/admin/users/{user_id}/revoke-sessions
# ===========================================================================


def test_admin_revoke_user_sessions(admin_client, mock_redis):
    """Admin revokes sessions for a specific user returns 200 OK."""
    with patch("routes.admin_sessions.require_admin_ops", new_callable=AsyncMock):
        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
            r = admin_client.post(f"/v1/admin/users/{TARGET_USER_ID}/revoke-sessions")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["user_id"] == TARGET_USER_ID
    assert "revoked" in body["detail"].lower()
    assert "86400" in body["detail"]


def test_non_admin_revoke_user_sessions_403(regular_client):
    """Non-admin user gets 403 when trying to revoke sessions."""
    with patch(
        "routes.admin_sessions.require_admin_ops",
        new_callable=AsyncMock,
        side_effect=HTTPException(status_code=403, detail="Acesso restrito a administradores"),
    ):
        r = regular_client.post(f"/v1/admin/users/{TARGET_USER_ID}/revoke-sessions")

    assert r.status_code == 403


def test_revoke_user_sessions_redis_unavailable_503(admin_client):
    """Redis unavailable returns 503 (fail-open behavior)."""
    with patch("routes.admin_sessions.require_admin_ops", new_callable=AsyncMock):
        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=None):
            r = admin_client.post(f"/v1/admin/users/{TARGET_USER_ID}/revoke-sessions")

    assert r.status_code == 503
    body = r.json()
    assert "redis" in body.get("detail", "").lower()


def test_revoke_user_sessions_redis_key_set_correctly(admin_client, mock_redis):
    """Redis session_revoke key is set with correct prefix, TTL and value."""
    with patch("routes.admin_sessions.require_admin_ops", new_callable=AsyncMock):
        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
            r = admin_client.post(f"/v1/admin/users/{TARGET_USER_ID}/revoke-sessions")

    assert r.status_code == 200

    expected_key = f"{_REVOKE_KEY_PREFIX}{TARGET_USER_ID}"
    mock_redis.setex.assert_called_once()

    call_args = mock_redis.setex.call_args
    assert call_args[0][0] == expected_key
    assert call_args[0][1] == _REVOKE_TTL

    # Third arg is a timestamp string — validate it looks like a unix timestamp
    ts_str = call_args[0][2]
    assert ts_str.isdigit(), f"Expected numeric timestamp, got {ts_str}"
    parsed = int(ts_str)
    now = int(time.time())
    assert abs(parsed - now) < 5, "Timestamp should be within 5s of now"


# ===========================================================================
# POST /v1/admin/revoke-all-sessions
# ===========================================================================


def test_master_revoke_all_sessions(admin_client, mock_redis):
    """Master revokes all sessions globally returns 200 OK with reason."""
    with patch("routes.admin_sessions.require_admin_ops", new_callable=AsyncMock):
        with patch("routes.admin_sessions.has_master_access", new_callable=AsyncMock, return_value=True):
            with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
                r = admin_client.post(
                    "/v1/admin/revoke-all-sessions",
                    json={"reason": "Teste de seguranca — incidente simulado"},
                )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "revoked_at" in body
    assert body["reason"] == "Teste de seguranca — incidente simulado"

    # Validate that the global_revoke_ts key was set
    mock_redis.set.assert_called_once()
    call_args = mock_redis.set.call_args
    assert call_args[0][0] == _GLOBAL_REVOKE_KEY


def test_master_revoke_all_sessions_default_reason(admin_client, mock_redis):
    """Master revokes all sessions without explicit reason uses default."""
    with patch("routes.admin_sessions.require_admin_ops", new_callable=AsyncMock):
        with patch("routes.admin_sessions.has_master_access", new_callable=AsyncMock, return_value=True):
            with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
                r = admin_client.post("/v1/admin/revoke-all-sessions", json={})

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "revoked_at" in body
    assert "master" in body["reason"].lower()


def test_non_master_admin_global_revoke_403(admin_client):
    """Non-master admin trying global revocation gets 403."""
    with patch("routes.admin_sessions.require_admin_ops", new_callable=AsyncMock):
        with patch("routes.admin_sessions.has_master_access", new_callable=AsyncMock, return_value=False):
            r = admin_client.post("/v1/admin/revoke-all-sessions", json={})

    assert r.status_code == 403
    body = r.json()
    assert "master" in body.get("detail", "").lower()


def test_global_revoke_redis_unavailable_503(admin_client):
    """Redis unavailable during global revocation returns 503."""
    with patch("routes.admin_sessions.require_admin_ops", new_callable=AsyncMock):
        with patch("routes.admin_sessions.has_master_access", new_callable=AsyncMock, return_value=True):
            with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=None):
                r = admin_client.post("/v1/admin/revoke-all-sessions", json={})

    assert r.status_code == 503
    body = r.json()
    assert "redis" in body.get("detail", "").lower()


def test_global_revoke_clears_l2_auth_cache(admin_client, mock_redis):
    """Global revocation clears L2 auth cache entries (smartlic:auth:* keys)."""
    mock_redis.keys = AsyncMock(return_value=["smartlic:auth:abc123", "smartlic:auth:def456"])

    with patch("routes.admin_sessions.require_admin_ops", new_callable=AsyncMock):
        with patch("routes.admin_sessions.has_master_access", new_callable=AsyncMock, return_value=True):
            with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
                r = admin_client.post("/v1/admin/revoke-all-sessions", json={})

    assert r.status_code == 200
    mock_redis.keys.assert_called_once_with("smartlic:auth:*")
    mock_redis.delete.assert_called_once_with("smartlic:auth:abc123", "smartlic:auth:def456")
