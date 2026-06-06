"""Tests for DIGEST-004: PATCH /conta/preferencias frequency toggle.

Tests the endpoint in routes/conta.py which allows authenticated users
to toggle their digest email frequency.

Design notes:
- Endpoint uses admin client (get_supabase) — no RLS, explicit .eq("user_id")
- Uses _run_with_budget() for DB write budget compliance
- Follows same test patterns as test_alert_preferences.py
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.conta import router
from auth import require_auth


# ============================================================================
# Fixtures
# ============================================================================

def _mock_user():
    return {"id": "test-user-123", "email": "test@example.com"}


@pytest.fixture
def app():
    """Create a test FastAPI app with conta router."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/v1")
    return test_app


@pytest.fixture
def client(app):
    """Create test client with auth override."""
    app.dependency_overrides[require_auth] = lambda: _mock_user()
    yield TestClient(app)
    app.dependency_overrides.clear()


# ============================================================================
# PATCH /v1/conta/preferencias
# ============================================================================

class TestUpdatePreferencias:
    """Test PATCH /conta/preferencias — frequency toggle."""

    PATCH_PATH = "/v1/conta/preferencias"

    def test_sets_daily_frequency(self, app, client):
        """PATCH with 'daily' updates frequency and returns it."""
        mock_sb = MagicMock()
        result = MagicMock()
        result.data = [{
            "user_id": "test-user-123",
            "frequency": "daily",
            "enabled": True,
            "last_digest_sent_at": None,
        }]
        mock_sb.table.return_value.upsert.return_value.execute.return_value = result

        with patch("routes.conta.get_supabase", return_value=mock_sb):
            response = client.patch(self.PATCH_PATH, json={"frequency": "daily"})

        assert response.status_code == 200
        data = response.json()
        assert data["frequency"] == "daily"
        assert data["enabled"] is True
        assert data["last_digest_sent_at"] is None

    def test_sets_weekly_frequency(self, app, client):
        mock_sb = MagicMock()
        result = MagicMock()
        result.data = [{
            "frequency": "weekly",
            "enabled": True,
            "last_digest_sent_at": None,
        }]
        mock_sb.table.return_value.upsert.return_value.execute.return_value = result

        with patch("routes.conta.get_supabase", return_value=mock_sb):
            response = client.patch(self.PATCH_PATH, json={"frequency": "weekly"})

        assert response.status_code == 200
        assert response.json()["frequency"] == "weekly"

    def test_sets_twice_weekly_frequency(self, app, client):
        mock_sb = MagicMock()
        result = MagicMock()
        result.data = [{
            "frequency": "twice_weekly",
            "enabled": True,
            "last_digest_sent_at": None,
        }]
        mock_sb.table.return_value.upsert.return_value.execute.return_value = result

        with patch("routes.conta.get_supabase", return_value=mock_sb):
            response = client.patch(self.PATCH_PATH, json={"frequency": "twice_weekly"})

        assert response.status_code == 200
        assert response.json()["frequency"] == "twice_weekly"

    def test_sets_off_frequency__returns_off(self, app, client):
        """DIGEST-001: API accepts 'off', normalizes to 'none' in DB, returns 'off'."""
        mock_sb = MagicMock()
        result = MagicMock()
        result.data = [{
            "frequency": "none",
            "enabled": True,
            "last_digest_sent_at": None,
        }]
        mock_sb.table.return_value.upsert.return_value.execute.return_value = result

        with patch("routes.conta.get_supabase", return_value=mock_sb):
            response = client.patch(self.PATCH_PATH, json={"frequency": "off"})

        assert response.status_code == 200
        data = response.json()
        # API contract: returns "off" (normalized from DB "none")
        assert data["frequency"] == "off"
        assert data["enabled"] is True

        # Verify DB write used "none", not "off"
        upsert_kwargs = mock_sb.table.return_value.upsert.call_args[0][0]
        assert upsert_kwargs["frequency"] == "none"

    def test_accepts_none_as_frequency(self, app, client):
        """DIGEST-004: API accepts 'none' directly (synonym for off)."""
        mock_sb = MagicMock()
        result = MagicMock()
        result.data = [{
            "frequency": "none",
            "enabled": True,
            "last_digest_sent_at": None,
        }]
        mock_sb.table.return_value.upsert.return_value.execute.return_value = result

        with patch("routes.conta.get_supabase", return_value=mock_sb):
            response = client.patch(self.PATCH_PATH, json={"frequency": "none"})

        assert response.status_code == 200
        # API normalizes "none" → "off" in response
        assert response.json()["frequency"] == "off"

    def test_rejects_invalid_frequency(self, app, client):
        """PATCH with invalid frequency returns 422."""
        mock_sb = MagicMock()
        with patch("routes.conta.get_supabase", return_value=mock_sb):
            response = client.patch(self.PATCH_PATH, json={"frequency": "hourly"})

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        # Pydantic field_validator raises ValueError → 422 via FastAPI
        assert any("Frequência" in str(e) for e in (
            error_detail if isinstance(error_detail, list) else [error_detail]
        ))

    def test_handles_db_error(self, app, client):
        """DB failure returns 500."""
        mock_sb = MagicMock()
        mock_sb.table.return_value.upsert.return_value.execute.side_effect = Exception("DB error")

        with patch("routes.conta.get_supabase", return_value=mock_sb):
            response = client.patch(self.PATCH_PATH, json={"frequency": "daily"})

        assert response.status_code == 500
        data = response.json()
        assert "Erro ao salvar" in data["detail"]

    def test_requires_authentication(self, app):
        """Without auth override, should fail with 401/403."""
        app.dependency_overrides.clear()
        client_no_auth = TestClient(app, raise_server_exceptions=False)
        response = client_no_auth.patch(self.PATCH_PATH, json={"frequency": "daily"})
        assert response.status_code in (401, 403)

    def test_upsert_creates_row_if_not_exists(self, app, client):
        """PATCH creates a new row when none exists (upsert)."""
        mock_sb = MagicMock()
        result = MagicMock()
        result.data = [{
            "user_id": "test-user-123",
            "frequency": "daily",
            "enabled": True,
            "last_digest_sent_at": None,
        }]
        mock_sb.table.return_value.upsert.return_value.execute.return_value = result

        with patch("routes.conta.get_supabase", return_value=mock_sb):
            response = client.patch(self.PATCH_PATH, json={"frequency": "daily"})

        assert response.status_code == 200
        assert response.json()["frequency"] == "daily"

        # Verify upsert was called with the right on_conflict
        upsert_call = mock_sb.table.return_value.upsert
        assert upsert_call.call_count == 1
        kwargs = upsert_call.call_args[1]
        assert kwargs.get("on_conflict") == "user_id"

    def test_response_shape_matches_schema(self, app, client):
        """Response contains all expected fields."""
        mock_sb = MagicMock()
        result = MagicMock()
        result.data = [{
            "frequency": "daily",
            "enabled": True,
            "last_digest_sent_at": "2026-06-06T10:00:00+00:00",
        }]
        mock_sb.table.return_value.upsert.return_value.execute.return_value = result

        with patch("routes.conta.get_supabase", return_value=mock_sb):
            response = client.patch(self.PATCH_PATH, json={"frequency": "daily"})

        assert response.status_code == 200
        data = response.json()
        # All three fields must be present
        assert "frequency" in data
        assert "enabled" in data
        assert "last_digest_sent_at" in data
        # last_digest_sent_at is preserved from DB
        assert data["last_digest_sent_at"] == "2026-06-06T10:00:00+00:00"
