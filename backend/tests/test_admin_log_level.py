"""#1923: Tests for /v1/admin/log-level runtime log toggle.

Covers:
- POST valid log level -> 200 OK, level changed
- POST invalid log level -> 422 validation error
- GET returns current overrides (empty at start)
- GET returns overrides after setting
- Non-admin user -> 403 Forbidden
- TTL expiry auto-reverts level (simulated expiry)
- Per-module override (specific logger, not root)
"""

from __future__ import annotations

import logging
import time

import pytest
from fastapi.testclient import TestClient

from admin import require_admin
from auth import require_auth
from main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_log_level_state():
    """Clear _log_level_overrides before each test to prevent cross-test leaks.

    Reverts any logger levels that were changed by previous tests.
    """
    from routes.admin_log_level import _log_level_overrides, _resolve_logger

    # Revert any lingering overrides
    for log_name, state in list(_log_level_overrides.items()):
        _resolve_logger(log_name).setLevel(state["original_level"])
    _log_level_overrides.clear()
    yield
    # Cleanup again after test
    for log_name, state in list(_log_level_overrides.items()):
        _resolve_logger(log_name).setLevel(state["original_level"])
    _log_level_overrides.clear()


@pytest.fixture
def admin_client():
    """TestClient with auth + admin bypass via dependency overrides.

    IMPORTANT: never ``patch('routes.X.require_auth')`` — breaks on startup.
    """
    fake_admin = {"id": "00000000-0000-0000-0000-00000000a001", "email": "admin@test"}
    app.dependency_overrides[require_auth] = lambda: fake_admin
    app.dependency_overrides[require_admin] = lambda: fake_admin
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def regular_client():
    """Logged-in non-admin user — should get 403 from require_admin."""
    fake_user = {"id": "regular-user-id", "email": "user@test"}
    app.dependency_overrides[require_auth] = lambda: fake_user
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)


# ---------------------------------------------------------------------------
# POST /v1/admin/log-level
# ---------------------------------------------------------------------------


class TestSetLogLevel:
    """POST /v1/admin/log-level — set runtime log level override."""

    def test_valid_level_returns_200(self, admin_client):
        """Set log level to DEBUG -> 200, level reflected in response."""
        r = admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "ttl_minutes": 5},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["current_level"] == "DEBUG"
        assert body["logger"] == "*"
        assert body["ttl_minutes"] == 5
        assert "reverts in 5 min" in body["detail"]

    def test_valid_level_actually_changes_logger(self, admin_client):
        """After POST, the root logger level is physically changed to the new value."""
        from routes.admin_log_level import _resolve_logger

        root_logger = _resolve_logger("*")
        original_level = root_logger.level

        admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "ttl_minutes": 5},
        )
        assert root_logger.level == logging.DEBUG

        # Restore for test isolation (in case reset fixture fails)
        root_logger.setLevel(original_level)

    def test_invalid_level_returns_422(self, admin_client):
        """Unknown level name -> 422 with descriptive error."""
        r = admin_client.post(
            "/v1/admin/log-level",
            json={"level": "BOGUS", "ttl_minutes": 5},
        )
        assert r.status_code == 422
        body = r.json()
        assert "Invalid log level" in body["detail"]

    def test_case_insensitive_level(self, admin_client):
        """'debug' (lowercase) is accepted and normalized to DEBUG."""
        r = admin_client.post(
            "/v1/admin/log-level",
            json={"level": "debug", "ttl_minutes": 5},
        )
        assert r.status_code == 200
        assert r.json()["current_level"] == "DEBUG"

    def test_module_specific_override(self, admin_client):
        """Setting level on a named module only affects that logger, not the root."""
        from routes.admin_log_level import _resolve_logger

        logger_name = "__test_admin_log_level_mod"
        module_logger = logging.getLogger(logger_name)
        module_logger.setLevel(logging.ERROR)

        r = admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "module": logger_name, "ttl_minutes": 5},
        )
        assert r.status_code == 200
        assert r.json()["logger"] == logger_name
        assert r.json()["current_level"] == "DEBUG"
        assert _resolve_logger(logger_name).level == logging.DEBUG

    def test_empty_module_uses_root_logger(self, admin_client):
        """Empty or whitespace-only module resolves to root logger (*)."""
        r = admin_client.post(
            "/v1/admin/log-level",
            json={"level": "INFO", "module": "", "ttl_minutes": 5},
        )
        assert r.status_code == 200
        assert r.json()["logger"] == "*"

    def test_whitespace_module_uses_root_logger(self, admin_client):
        """Module with only spaces resolves to root logger (*)."""
        r = admin_client.post(
            "/v1/admin/log-level",
            json={"level": "INFO", "module": "   ", "ttl_minutes": 5},
        )
        assert r.status_code == 200
        assert r.json()["logger"] == "*"

    def test_preserves_original_level_on_second_set(self, admin_client):
        """Second POST on same logger keeps original level captured by first POST.

        If a logger was at WARNING initially, then set to DEBUG, then set to INFO,
        the original_level should still be WARNING -- not INFO.
        """
        from routes.admin_log_level import _log_level_overrides

        logger_name = "__test_admin_double_set"
        logging.getLogger(logger_name).setLevel(logging.WARNING)

        admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "module": logger_name, "ttl_minutes": 10},
        )
        admin_client.post(
            "/v1/admin/log-level",
            json={"level": "INFO", "module": logger_name, "ttl_minutes": 10},
        )

        assert _log_level_overrides[logger_name]["original_level"] == logging.WARNING

    def test_min_ttl_is_1_minute(self, admin_client):
        """ttl_minutes=0 is rejected (< field ge=1)."""
        r = admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "ttl_minutes": 0},
        )
        assert r.status_code == 422

    def test_max_ttl_is_1440_minutes(self, admin_client):
        """ttl_minutes=1441 is rejected (> field le=1440)."""
        r = admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "ttl_minutes": 1441},
        )
        assert r.status_code == 422

    def test_audit_log_on_change(self, admin_client, caplog):
        """Setting log level logs an ADMIN LOG LEVEL CHANGE message."""
        caplog.set_level(logging.INFO)

        admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "ttl_minutes": 5},
        )

        assert any(
            "ADMIN LOG LEVEL CHANGE" in record.message
            for record in caplog.records
        )


# ---------------------------------------------------------------------------
# GET /v1/admin/log-level
# ---------------------------------------------------------------------------


class TestGetLogLevel:
    """GET /v1/admin/log-level -- list current overrides."""

    def test_returns_empty_at_start(self, admin_client):
        """GET returns count=0, overrides=[] when no level changes have been made."""
        r = admin_client.get("/v1/admin/log-level")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 0
        assert body["overrides"] == []

    def test_returns_active_overrides_after_set(self, admin_client):
        """GET returns the override entry after POST sets a level."""
        admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "ttl_minutes": 10},
        )

        r = admin_client.get("/v1/admin/log-level")
        assert r.status_code == 200
        body = r.json()
        assert body["count"] == 1

        override = body["overrides"][0]
        assert override["logger"] == "*"
        assert override["current_level"] == "DEBUG"
        assert override["ttl_remaining_seconds"] is not None
        assert override["ttl_remaining_seconds"] > 0
        assert override["set_by"] == "00000000-0000-0000-0000-00000000a001"

    def test_multiple_overrides_returned(self, admin_client):
        """GET returns all overrides when multiple loggers are changed."""
        from routes.admin_log_level import _log_level_overrides

        _log_level_overrides["mod_a"] = {
            "original_level": logging.INFO,
            "current_level": logging.DEBUG,
            "set_by": "admin",
            "set_at": "now",
            "ttl_until": time.monotonic() + 600,
        }
        _log_level_overrides["mod_b"] = {
            "original_level": logging.WARNING,
            "current_level": logging.ERROR,
            "set_by": "admin",
            "set_at": "now",
            "ttl_until": None,
        }

        r = admin_client.get("/v1/admin/log-level")
        assert r.status_code == 200
        assert r.json()["count"] == 2
        loggers = {o["logger"] for o in r.json()["overrides"]}
        assert loggers == {"mod_a", "mod_b"}

    def test_ttl_remaining_shows_zero_when_expired(self, admin_client):
        """Expired override shows ttl_remaining_seconds = 0 (never negative)."""
        from routes.admin_log_level import _log_level_overrides

        _log_level_overrides["expired_mod"] = {
            "original_level": logging.INFO,
            "current_level": logging.DEBUG,
            "set_by": "admin",
            "set_at": "now",
            "ttl_until": time.monotonic() - 60,  # expired 60 seconds ago
        }

        r = admin_client.get("/v1/admin/log-level")
        assert r.status_code == 200
        override = r.json()["overrides"][0]
        assert override["ttl_remaining_seconds"] == 0
        assert override["logger"] == "expired_mod"

    def test_ttl_none_when_no_expiry(self, admin_client):
        """Override with ttl_until=None shows null ttl_remaining_seconds."""
        from routes.admin_log_level import _log_level_overrides

        _log_level_overrides["no_ttl"] = {
            "original_level": logging.INFO,
            "current_level": logging.DEBUG,
            "set_by": "admin",
            "set_at": "now",
            "ttl_until": None,
        }

        r = admin_client.get("/v1/admin/log-level")
        assert r.status_code == 200
        override = r.json()["overrides"][0]
        assert override["ttl_remaining_seconds"] is None

    def test_original_level_preserved_in_get(self, admin_client):
        """GET shows original_level != current_level when override is active."""
        from routes.admin_log_level import _resolve_logger

        logger_name = "__test_admin_original_in_get"
        _resolve_logger(logger_name).setLevel(logging.WARNING)

        admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "module": logger_name, "ttl_minutes": 10},
        )

        r = admin_client.get("/v1/admin/log-level")
        override = r.json()["overrides"][0]
        assert override["original_level"] == "WARNING"
        assert override["current_level"] == "DEBUG"


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------


class TestAuthorization:
    """Non-admin users must be rejected with 403 on all endpoints."""

    def test_post_rejects_non_admin(self, regular_client):
        """Regular user gets 403 on POST /v1/admin/log-level."""
        r = regular_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG"},
        )
        assert r.status_code == 403

    def test_get_rejects_non_admin(self, regular_client):
        """Regular user gets 403 on GET /v1/admin/log-level."""
        r = regular_client.get("/v1/admin/log-level")
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# TTL auto-revert
# ---------------------------------------------------------------------------


class TestTTLExpiry:
    """TTL expiry logic -- override is reverted after TTL passes.

    The background task ``_periodic_log_level_ttl_checker`` runs every 30s
    in production. These tests simulate the reversion logic directly to
    verify the algorithm without the 30s polling delay.
    """

    def test_ttl_expiry_reverts_log_level(self, admin_client):
        """When TTL expires, the logger reverts to its original level."""
        from routes.admin_log_level import (
            _log_level_overrides,
            _resolve_logger,
        )

        logger_name = "__test_admin_ttl_revert"
        test_logger = logging.getLogger(logger_name)
        test_logger.setLevel(logging.WARNING)
        original_level = test_logger.level

        # Set to DEBUG via endpoint
        admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "module": logger_name, "ttl_minutes": 1},
        )
        assert test_logger.level == logging.DEBUG

        # Manually expire the TTL
        _log_level_overrides[logger_name]["ttl_until"] = time.monotonic() - 1

        # Run the same reversion logic as _periodic_log_level_ttl_checker
        now_mono = time.monotonic()
        expired = [
            name
            for name, state in list(_log_level_overrides.items())
            if state.get("ttl_until") is not None and now_mono >= state["ttl_until"]
        ]

        for name in expired:
            state = _log_level_overrides.pop(name, None)
            if state is not None:
                _resolve_logger(name).setLevel(state["original_level"])

        # Verify revert
        assert test_logger.level == original_level
        assert logger_name not in _log_level_overrides

    def test_non_expired_override_not_reverted(self, admin_client):
        """Override with non-expired TTL is preserved -- not reverted."""
        from routes.admin_log_level import (
            _log_level_overrides,
            _resolve_logger,
        )

        logger_name = "__test_admin_ttl_kept"
        test_logger = logging.getLogger(logger_name)
        test_logger.setLevel(logging.ERROR)

        # Set via endpoint
        admin_client.post(
            "/v1/admin/log-level",
            json={"level": "DEBUG", "module": logger_name, "ttl_minutes": 60},
        )
        assert test_logger.level == logging.DEBUG

        # Set TTL far in the future
        _log_level_overrides[logger_name]["ttl_until"] = time.monotonic() + 3600

        # Run reversion logic
        now_mono = time.monotonic()
        expired = [
            name
            for name, state in list(_log_level_overrides.items())
            if state.get("ttl_until") is not None and now_mono >= state["ttl_until"]
        ]

        # No overrides should be expired
        assert len(expired) == 0
        assert logger_name in _log_level_overrides
        assert test_logger.level == logging.DEBUG
