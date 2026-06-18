"""Tests for Issue #1973 granular rate limiting features.

Tests cover:
- resolve_user_tier function
- _check_granular_rate_limit behavior
- Feature flag integration through config module
"""

import base64
import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Request


def _make_request(path: str = "/test", auth_header: str = "") -> Request:
    """Helper to create a mock Request with optional auth header."""
    headers_list = []
    if auth_header:
        headers_list.append((b"authorization", auth_header.encode()))
    scope = {
        "type": "http",
        "method": "GET",
        "path": path,
        "headers": headers_list,
        "query_string": b"",
        "client": ("127.0.0.1", 50000),
        "scheme": "http",
        "server": ("test", 80),
        "state": {},
    }
    return Request(scope)


def _make_test_jwt(sub: str = "user-123") -> str:
    """Build a parseable JWT (not cryptographically valid)."""
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "HS256"}).encode()
    ).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(
        json.dumps({"sub": sub, "role": "authenticated"}).encode()
    ).rstrip(b"=").decode()
    return f"{header}.{payload}.signature"


class TestResolveUserTier:
    """Test the resolve_user_tier function."""

    def test_no_auth_returns_anonymous(self):
        """Should return anonymous when no auth header."""
        from rate_limiter import resolve_user_tier

        request = _make_request()
        assert resolve_user_tier(request) == "anonymous"

    def test_invalid_jwt_returns_anonymous(self):
        """Should return anonymous for unparseable JWT."""
        from rate_limiter import resolve_user_tier

        request = _make_request(auth_header="Bearer not-a-valid-token")
        assert resolve_user_tier(request) == "anonymous"

    def test_authenticated_returns_pro(self):
        """Should return pro for authenticated non-admin user."""
        from rate_limiter import resolve_user_tier

        jwt = _make_test_jwt(sub="user-abc-123")
        request = _make_request(auth_header=f"Bearer {jwt}")
        assert resolve_user_tier(request) == "pro"

    @patch.dict(os.environ, {"ADMIN_USER_IDS": "admin-123"})
    def test_admin_user_returns_admin(self):
        """Should return admin when user is in ADMIN_USER_IDS."""
        from rate_limiter import resolve_user_tier

        jwt = _make_test_jwt(sub="admin-123")
        request = _make_request(auth_header=f"Bearer {jwt}")
        assert resolve_user_tier(request) == "admin"


class TestGranularRateLimitCheck:
    """Test the _check_granular_rate_limit function."""

    @pytest.mark.asyncio
    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    async def test_exempt_endpoint_bypasses_check(self, mock_pool):
        """Exempt endpoints should not hit rate limit check."""
        from rate_limiter import _check_granular_rate_limit

        request = _make_request(path="/health")
        result = await _check_granular_rate_limit(request)
        assert result is None  # No return = skip

    @pytest.mark.asyncio
    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    async def test_allows_request_within_limit(self, mock_pool):
        """Should allow request when under rate limit."""
        from rate_limiter import _check_granular_rate_limit

        request = _make_request(path="/buscar")
        result = await _check_granular_rate_limit(request)
        assert result is None  # allowed

    @pytest.mark.asyncio
    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    async def test_sets_rate_limit_headers_on_success(self, mock_pool):
        """Should set X-RateLimit-* headers on request.state."""
        from rate_limiter import _check_granular_rate_limit

        request = _make_request(path="/buscar")
        await _check_granular_rate_limit(request)
        headers = getattr(request.state, "_rate_limit_headers", None)
        assert headers is not None
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers

    @pytest.mark.asyncio
    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    async def test_uses_compound_key_with_tier_and_endpoint(self, mock_pool):
        """Should use compound key format {tier}:{endpoint}:{identifier}."""
        from rate_limiter import _check_granular_rate_limit, _flexible_limiter

        request = _make_request(path="/buscar")

        # Patch to capture the key
        original_check = _flexible_limiter.check_rate_limit
        captured_key = None

        async def capturing_check(key, max_requests, window_seconds):
            nonlocal captured_key
            captured_key = key
            return await original_check(key, max_requests, window_seconds)

        _flexible_limiter.check_rate_limit = capturing_check

        await _check_granular_rate_limit(request)

        assert captured_key is not None
        # Key starts with "anonymous:/buscar:ip:"
        assert captured_key.startswith("anonymous:/buscar:ip:")


class TestRequireRateLimitGranular:
    """Test require_rate_limit with granular mode enabled.

    Uses mocking at the config module level because get_feature_flag is
    imported locally within the require_rate_limit closure.
    """

    @pytest.mark.asyncio
    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    @patch("config.get_feature_flag", return_value=True)
    async def test_granular_mode_skips_exempt_endpoints(self, mock_flag, mock_pool):
        """Exempt endpoints should pass through in granular mode."""
        from rate_limiter import require_rate_limit

        request = _make_request(path="/health")
        checker = require_rate_limit(10, 60)
        result = await checker(request)
        assert result is None

    @pytest.mark.asyncio
    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    @patch("config.get_feature_flag", return_value=True)
    async def test_granular_mode_allows_within_limit(self, mock_flag, mock_pool):
        """Should allow requests within granular limits."""
        from rate_limiter import require_rate_limit

        request = _make_request(path="/buscar")
        checker = require_rate_limit(10, 60)
        result = await checker(request)
        assert result is None

    @pytest.mark.asyncio
    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    @patch("config.get_feature_flag", return_value=True)
    async def test_granular_mode_sets_rate_limit_headers(self, mock_flag, mock_pool):
        """Should set rate limit headers via request.state."""
        from rate_limiter import require_rate_limit

        request = _make_request(path="/buscar")
        checker = require_rate_limit(10, 60)
        await checker(request)
        headers = getattr(request.state, "_rate_limit_headers", None)
        assert headers is not None
        assert "X-RateLimit-Limit" in headers

    @pytest.mark.asyncio
    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    @patch("config.get_feature_flag")
    async def test_legacy_mode_when_granular_disabled(self, mock_flag, mock_pool):
        """When granular is disabled, should use passed params (legacy mode)."""
        from rate_limiter import require_rate_limit

        # RATE_LIMITING_ENABLED=True, RATE_LIMIT_PER_ENDPOINT_ENABLED=False
        mock_flag.side_effect = [True, False]

        request = _make_request(path="/buscar", auth_header=f"Bearer {_make_test_jwt()}")
        checker = require_rate_limit(999, 60)
        result = await checker(request)
        assert result is None

    @pytest.mark.asyncio
    @patch("rate_limiter.get_redis_pool", new_callable=AsyncMock, return_value=None)
    @patch("config.get_feature_flag")
    async def test_disabled_flag_skips_granular(self, mock_flag, mock_pool):
        """When RATE_LIMITING_ENABLED is False, granular is skipped."""
        from rate_limiter import require_rate_limit

        # RATE_LIMITING_ENABLED=False — function returns early, never checks granular flag
        mock_flag.side_effect = [False]

        request = _make_request(path="/buscar")
        checker = require_rate_limit(10, 60)
        result = await checker(request)
        assert result is None
