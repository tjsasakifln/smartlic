"""Tests for LGPD data deletion routes (data_deletion.py).

#1804: LGPD data deletion flow with double opt-out (Art. 18).
Routes at /v1/me/* (registered in _v1_routers with prefix="/me").
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from main import app
from auth import require_auth


MOCK_USER_ID = "test-user-id-456"
MOCK_ADMIN_ID = "test-admin-id-789"
MOCK_USER = {"id": MOCK_USER_ID, "email": "user@test.com", "role": "authenticated"}
MOCK_ADMIN = {"id": MOCK_ADMIN_ID, "email": "admin@test.com", "role": "authenticated"}

client = TestClient(app)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Ensure dependency overrides are cleared after each test."""
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def auth_user():
    app.dependency_overrides[require_auth] = lambda: MOCK_USER
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def auth_admin():
    app.dependency_overrides[require_auth] = lambda: MOCK_ADMIN
    yield
    app.dependency_overrides.clear()


def _make_pending_record(token_hash: str, age_hours: float = 0) -> dict:
    """Create a mock pending deletion request record."""
    requested_at = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).isoformat()
    return {
        "id": "req-123",
        "deletion_token": token_hash,
        "requested_at": requested_at,
    }


def _make_hash(raw_token: str) -> str:
    """Compute deletion hash using the same logic as the route."""
    from routes.data_deletion import _make_deletion_hash
    return _make_deletion_hash(raw_token)


# ─── Helpers: mock supabase ───────────────────────────────────────────────────

def _mock_sb_client(get_sb_mock, sb_execute_mock):
    """Configure _get_sb AsyncMock to return a usable supabase client mock."""
    get_sb_mock.return_value = MagicMock()


# ─── POST /v1/me/request-deletion ─────────────────────────────────────────────

class TestRequestDeletion:
    """POST /v1/me/request-deletion — solicita exclusao."""

    @patch("email_service.send_email")
    @patch("routes.data_deletion._sb_execute", new_callable=AsyncMock)
    @patch("routes.data_deletion._get_sb", new_callable=AsyncMock)
    def test_request_deletion_success(
        self, mock_get_sb, mock_sb_execute, mock_send_email, auth_user
    ):
        """Should return 200 with pending status when no existing request."""
        mock_get_sb.return_value = MagicMock()

        # First _sb_execute: check existing pending — none found
        # Second _sb_execute: insert new request
        mock_sb_execute.side_effect = [
            MagicMock(data=[]),  # no existing pending
            MagicMock(data=[]),  # insert ok
        ]

        response = client.post("/v1/me/request-deletion")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert "email" in data["detail"].lower()

    @patch("email_service.send_email")
    @patch("routes.data_deletion._sb_execute", new_callable=AsyncMock)
    @patch("routes.data_deletion._get_sb", new_callable=AsyncMock)
    def test_request_deletion_idempotent(
        self, mock_get_sb, mock_sb_execute, mock_send_email, auth_user
    ):
        """Should return 200 with already_pending when request already exists."""
        mock_get_sb.return_value = MagicMock()

        mock_sb_execute.return_value = MagicMock(data=[{"id": "req-123", "status": "pending"}])

        response = client.post("/v1/me/request-deletion")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "already_pending"
        assert mock_sb_execute.call_count <= 1  # only check, no insert

    def test_request_deletion_requires_auth(self):
        """Should return 401/403 when not authenticated."""
        response = client.post("/v1/me/request-deletion")
        assert response.status_code in (401, 403)


# ─── POST /v1/me/confirm-deletion ─────────────────────────────────────────────

class TestConfirmDeletion:
    """POST /v1/me/confirm-deletion — confirma com token do email."""

    @patch("routes.data_deletion._sb_execute", new_callable=AsyncMock)
    @patch("routes.data_deletion._get_sb", new_callable=AsyncMock)
    def test_confirm_deletion_valid_token(
        self, mock_get_sb, mock_sb_execute, auth_user
    ):
        """Should return 200 with completed status when token is valid."""
        mock_get_sb.return_value = MagicMock()

        raw_token = "valid-test-token-456"
        token_hash = _make_hash(raw_token)

        # Three _sb_execute calls:
        #   1. find pending request
        #   2. update profile (soft-delete)
        #   3. update request status -> completed
        mock_sb_execute.side_effect = [
            MagicMock(data=[_make_pending_record(token_hash)]),
            MagicMock(data=[]),
            MagicMock(data=[]),
        ]

        response = client.post("/v1/me/confirm-deletion", json={"token": raw_token})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

    @patch("routes.data_deletion._sb_execute", new_callable=AsyncMock)
    @patch("routes.data_deletion._get_sb", new_callable=AsyncMock)
    def test_confirm_deletion_invalid_token(
        self, mock_get_sb, mock_sb_execute, auth_user
    ):
        """Should return 403 when token does not match."""
        mock_get_sb.return_value = MagicMock()

        actual_hash = _make_hash("real-token")
        mock_sb_execute.return_value = MagicMock(data=[
            _make_pending_record(actual_hash)
        ])

        response = client.post("/v1/me/confirm-deletion", json={"token": "wrong-token"})

        assert response.status_code == 403
        assert "Token inválido" in response.json()["detail"]

    @patch("routes.data_deletion._sb_execute", new_callable=AsyncMock)
    @patch("routes.data_deletion._get_sb", new_callable=AsyncMock)
    def test_confirm_deletion_no_pending(
        self, mock_get_sb, mock_sb_execute, auth_user
    ):
        """Should return 404 when no pending deletion request exists."""
        mock_get_sb.return_value = MagicMock()

        mock_sb_execute.return_value = MagicMock(data=[])

        response = client.post("/v1/me/confirm-deletion", json={"token": "any-token"})

        assert response.status_code == 404
        assert "Nenhuma" in response.json()["detail"]

    @patch("routes.data_deletion._sb_execute", new_callable=AsyncMock)
    @patch("routes.data_deletion._get_sb", new_callable=AsyncMock)
    def test_confirm_deletion_expired_token(
        self, mock_get_sb, mock_sb_execute, auth_user
    ):
        """Should return 410 when token is older than 24h."""
        mock_get_sb.return_value = MagicMock()

        token_hash = _make_hash("expired-token")
        mock_sb_execute.return_value = MagicMock(data=[
            _make_pending_record(token_hash, age_hours=25)
        ])

        response = client.post("/v1/me/confirm-deletion", json={"token": "expired-token"})

        assert response.status_code == 410
        assert "expirado" in response.json()["detail"].lower()


# ─── POST /v1/me/cancel-deletion ──────────────────────────────────────────────

class TestCancelDeletion:
    """POST /v1/me/cancel-deletion — cancela solicitacao."""

    @patch("routes.data_deletion._sb_execute", new_callable=AsyncMock)
    @patch("routes.data_deletion._get_sb", new_callable=AsyncMock)
    def test_cancel_deletion_success(
        self, mock_get_sb, mock_sb_execute, auth_user
    ):
        """Should return 200 with cancelled status."""
        mock_get_sb.return_value = MagicMock()

        mock_sb_execute.return_value = MagicMock(data=[])

        response = client.post("/v1/me/cancel-deletion")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert "cancelada" in data["detail"].lower()


# ─── DELETE /v1/me/admin/{user_id} ────────────────────────────────────────────

class TestAdminDeleteUser:
    """DELETE /v1/me/admin/{user_id} — admin force-deletion."""

    @patch("routes.data_deletion.is_admin", new_callable=AsyncMock, return_value=True)
    @patch("routes.data_deletion._sb_execute", new_callable=AsyncMock)
    @patch("routes.data_deletion._get_sb", new_callable=AsyncMock)
    def test_admin_delete_success(
        self, mock_get_sb, mock_sb_execute, mock_is_admin, auth_admin
    ):
        """Should return 200 when admin force-deletes a user."""
        mock_get_sb.return_value = MagicMock()

        mock_sb_execute.return_value = MagicMock(data=[])

        response = client.delete(f"/v1/me/admin/{MOCK_USER_ID}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"

        # Verify soft-delete: _sb_execute called with profile update
        assert mock_sb_execute.called

    @patch("routes.data_deletion.is_admin", new_callable=AsyncMock, return_value=False)
    @patch("routes.data_deletion._sb_execute", new_callable=AsyncMock)
    @patch("routes.data_deletion._get_sb", new_callable=AsyncMock)
    def test_admin_delete_non_admin(
        self, mock_get_sb, mock_sb_execute, mock_is_admin, auth_user
    ):
        """Should return 403 when non-admin tries to force-delete."""
        mock_get_sb.return_value = MagicMock()

        response = client.delete(f"/v1/me/admin/{MOCK_USER_ID}")

        assert response.status_code == 403
        assert "Apenas administradores" in response.json()["detail"]
        assert not mock_sb_execute.called  # no DB operation

    def test_admin_delete_requires_auth(self):
        """Should return 401/403 when not authenticated."""
        response = client.delete(f"/v1/me/admin/{MOCK_USER_ID}")
        assert response.status_code in (401, 403)
