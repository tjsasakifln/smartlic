"""Tests for STORY-278 AC6: Alert Preferences endpoint.

Tests GET/PUT /v1/profile/alert-preferences in routes/user.py.

SYS-023: Alert preferences endpoints now use get_user_db (user-scoped client).
Tests override get_user_db with mock_db to maintain the same testing pattern.
"""

import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from routes.user import router
from auth import require_auth
from database import get_db, get_user_db


# ============================================================================
# Fixtures
# ============================================================================

def _mock_user():
    return {"id": "test-user-123", "email": "test@example.com"}


@pytest.fixture
def app():
    """Create a test FastAPI app with user router."""
    test_app = FastAPI()
    test_app.include_router(router, prefix="/v1")
    return test_app


@pytest.fixture
def client(app):
    """Create test client with auth override."""
    app.dependency_overrides[require_auth] = lambda: _mock_user()
    yield TestClient(app)
    app.dependency_overrides.clear()


def _override_db(app, mock_db):
    """Helper to override both get_db and get_user_db with the same mock."""
    app.dependency_overrides[get_db] = lambda: mock_db
    # SYS-023: Alert preferences endpoints now use get_user_db
    app.dependency_overrides[get_user_db] = lambda: mock_db


# ============================================================================
# GET /v1/profile/alert-preferences
# ============================================================================

class TestGetAlertPreferences:
    """Test fetching alert preferences."""

    def test_returns_existing_preferences(self, app, client):
        mock_db = MagicMock()
        result = MagicMock()
        result.data = {
            "frequency": "twice_weekly",
            "enabled": False,
            "last_digest_sent_at": "2026-02-25T10:00:00+00:00",
        }
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = result
        _override_db(app, mock_db)

        response = client.get("/v1/profile/alert-preferences")

        assert response.status_code == 200
        data = response.json()
        assert data["frequency"] == "twice_weekly"
        assert data["enabled"] is False
        assert data["last_digest_sent_at"] == "2026-02-25T10:00:00+00:00"

    def test_returns_defaults_when_no_record(self, app, client):
        mock_db = MagicMock()
        result = MagicMock()
        result.data = None
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = result
        _override_db(app, mock_db)

        response = client.get("/v1/profile/alert-preferences")

        assert response.status_code == 200
        data = response.json()
        assert data["frequency"] == "daily"
        assert data["enabled"] is True
        assert data["last_digest_sent_at"] is None

    def test_returns_defaults_on_db_error(self, app, client):
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.side_effect = Exception("DB error")
        _override_db(app, mock_db)

        response = client.get("/v1/profile/alert-preferences")

        assert response.status_code == 200
        data = response.json()
        assert data["frequency"] == "daily"
        assert data["enabled"] is True

    def test_requires_auth(self, app):
        """Without auth override, should fail."""
        app.dependency_overrides.clear()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/v1/profile/alert-preferences")
        assert response.status_code in (401, 403, 422, 500)


# ============================================================================
# PUT /v1/profile/alert-preferences
# ============================================================================

class TestUpdateAlertPreferences:
    """Test updating alert preferences."""

    def test_updates_preferences(self, app, client):
        mock_db = MagicMock()
        result = MagicMock()
        result.data = [{
            "user_id": "test-user-123",
            "frequency": "weekly",
            "enabled": True,
            "last_digest_sent_at": None,
        }]
        mock_db.table.return_value.upsert.return_value.execute.return_value = result
        _override_db(app, mock_db)

        response = client.put("/v1/profile/alert-preferences", json={
            "frequency": "weekly",
            "enabled": True,
        })

        assert response.status_code == 200
        data = response.json()
        assert data["frequency"] == "weekly"
        assert data["enabled"] is True

    def test_rejects_invalid_frequency(self, app, client):
        mock_db = MagicMock()
        _override_db(app, mock_db)

        response = client.put("/v1/profile/alert-preferences", json={
            "frequency": "hourly",
            "enabled": True,
        })

        assert response.status_code == 400
        assert "invalida" in response.json()["detail"].lower()

    def test_updates_to_off__normalizes_to_none_in_db(self, app, client):
        """DIGEST-001: API accepts 'off', normalizes to 'none' in DB, returns 'off'."""
        mock_db = MagicMock()
        result = MagicMock()
        result.data = [{
            "user_id": "test-user-123",
            "frequency": "none",  # DB stores "none" per CHECK constraint
            "enabled": False,
            "last_digest_sent_at": None,
        }]
        mock_db.table.return_value.upsert.return_value.execute.return_value = result
        _override_db(app, mock_db)

        response = client.put("/v1/profile/alert-preferences", json={
            "frequency": "off",
            "enabled": False,
        })

        assert response.status_code == 200
        data = response.json()
        # API contract: returns "off" (normalized from DB "none")
        assert data["frequency"] == "off"
        assert data["enabled"] is False

        # Verify DB write used "none", not "off"
        upsert_kwargs = mock_db.table.return_value.upsert.call_args[0][0]
        assert upsert_kwargs["frequency"] == "none"

    def test_get_normalizes_none_to_off(self, app, client):
        """DIGEST-001: GET returns 'off' when DB stores 'none'."""
        mock_db = MagicMock()
        result = MagicMock()
        result.data = {
            "frequency": "none",  # DB value
            "enabled": True,
            "last_digest_sent_at": None,
        }
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = result
        _override_db(app, mock_db)

        response = client.get("/v1/profile/alert-preferences")

        assert response.status_code == 200
        data = response.json()
        # API contract: returns "off" (normalized from DB "none")
        assert data["frequency"] == "off"

    def test_handles_db_error(self, app, client):
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute.side_effect = Exception("DB error")
        _override_db(app, mock_db)

        response = client.put("/v1/profile/alert-preferences", json={
            "frequency": "daily",
            "enabled": True,
        })

        assert response.status_code == 500

    def test_accepts_twice_weekly(self, app, client):
        mock_db = MagicMock()
        result = MagicMock()
        result.data = [{
            "frequency": "twice_weekly",
            "enabled": True,
            "last_digest_sent_at": None,
        }]
        mock_db.table.return_value.upsert.return_value.execute.return_value = result
        _override_db(app, mock_db)

        response = client.put("/v1/profile/alert-preferences", json={
            "frequency": "twice_weekly",
            "enabled": True,
        })

        assert response.status_code == 200
        assert response.json()["frequency"] == "twice_weekly"

    def test_accepts_daily(self, app, client):
        mock_db = MagicMock()
        result = MagicMock()
        result.data = [{
            "frequency": "daily",
            "enabled": True,
            "last_digest_sent_at": None,
        }]
        mock_db.table.return_value.upsert.return_value.execute.return_value = result
        _override_db(app, mock_db)

        response = client.put("/v1/profile/alert-preferences", json={
            "frequency": "daily",
            "enabled": True,
        })

        assert response.status_code == 200


# ============================================================================
# Metrics tests
# ============================================================================

class TestDigestMetrics:
    """Test STORY-278 AC7: Prometheus metrics."""

    def test_digest_emails_sent_counter_exists(self):
        from metrics import DIGEST_EMAILS_SENT
        DIGEST_EMAILS_SENT.labels(status="success").inc()

    def test_digest_job_duration_histogram_exists(self):
        from metrics import DIGEST_JOB_DURATION
        DIGEST_JOB_DURATION.observe(1.5)
