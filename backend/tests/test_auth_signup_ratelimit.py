"""MED-SEC-001: Signup rate limiting tests.

Validates that signup-related endpoints enforce rate limits
to prevent trial multi-account abuse via FlexibleRateLimiter.
"""

import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _mock_audit():
    """Ensure audit.log_audit_event is importable (may not exist in test env)."""
    import audit
    if not hasattr(audit, "log_audit_event"):
        audit.log_audit_event = lambda **kwargs: None
    yield


def _make_app():
    """Create minimal FastAPI app with auth routers for isolated testing."""
    from routes.auth_email import router as email_router
    from routes.auth_check import router as check_router

    app = FastAPI()
    app.include_router(email_router)
    app.include_router(check_router)
    return app


class TestSignupRateLimiting:
    """MED-SEC-001: Validate signup endpoint rate limiting."""

    def test_validate_signup_email_works(self):
        """POST /auth/validate-signup-email returns 200 for valid email."""
        with patch("config.get_feature_flag", return_value=False):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/auth/validate-signup-email",
                    json={"email": "test@gmail.com"},
                )
                assert resp.status_code == 200
                assert resp.json()["valid"] is True

    def test_check_email_works(self):
        """GET /auth/check-email returns 200."""
        with patch("config.get_feature_flag", return_value=False):
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/auth/check-email?email=test@gmail.com")
                assert resp.status_code == 200
                data = resp.json()
                assert "available" in data

    def test_rate_limit_blocks_excess_signup(self):
        """MED-SEC-001: 4th signup validation in 10min returns 429."""
        call_count = 0

        async def mock_check(key, max_req, window):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                return (False, 600, 0)
            return (True, 0, max_req - 1)

        with patch("config.get_feature_flag", return_value=True), \
             patch("rate_limiter._flexible_limiter") as mock_limiter:
            mock_limiter.check_rate_limit = AsyncMock(side_effect=mock_check)
            app = _make_app()
            with TestClient(app) as client:
                for i in range(3):
                    resp = client.post(
                        "/auth/validate-signup-email",
                        json={"email": f"user{i}@gmail.com"},
                    )
                    assert resp.status_code == 200, f"Request {i+1} should succeed"

                resp = client.post(
                    "/auth/validate-signup-email",
                    json={"email": "user4@gmail.com"},
                )
                assert resp.status_code == 429

    def test_rate_limit_429_has_retry_after(self):
        """429 response includes retry_after_seconds and Retry-After header."""
        async def mock_check(key, max_req, window):
            return (False, 600, 0)

        with patch("config.get_feature_flag", return_value=True), \
             patch("rate_limiter._flexible_limiter") as mock_limiter:
            mock_limiter.check_rate_limit = AsyncMock(side_effect=mock_check)
            app = _make_app()
            with TestClient(app) as client:
                resp = client.post(
                    "/auth/validate-signup-email",
                    json={"email": "blocked@gmail.com"},
                )
                assert resp.status_code == 429
                body = resp.json()
                assert "retry_after_seconds" in body.get("detail", {})
                assert resp.headers.get("retry-after") == "600"

    def test_check_email_rate_limited(self):
        """GET /auth/check-email also rate limited under MED-SEC-001."""
        async def mock_check(key, max_req, window):
            return (False, 300, 0)

        with patch("config.get_feature_flag", return_value=True), \
             patch("rate_limiter._flexible_limiter") as mock_limiter:
            mock_limiter.check_rate_limit = AsyncMock(side_effect=mock_check)
            app = _make_app()
            with TestClient(app) as client:
                resp = client.get("/auth/check-email?email=test@gmail.com")
                assert resp.status_code == 429
