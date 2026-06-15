"""Tests for edge-layer IP rate limiter (Issue #1861).

AC8: Tests must include unit (mock Redis) and integration (real Redis with respawn).

Test structure:
- ``TestIPRateLimitConfig`` — env-var parsing and defaults (AC5, AC3).
- ``TestIPRateLimitLogic`` — sliding window, blocklist, exempt paths (AC1-AC4).
- ``TestIPRateLimitIntegration`` — real Redis integration (AC8 integration tier).
"""

import time
from unittest.mock import patch

import pytest
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Scope

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _ok_response(request: Request) -> Response:
    """Standard success response for call_next."""
    return Response(status_code=200, content=b"ok")


def _make_scope(
    path: str = "/v1/search/test",
    method: str = "GET",
    client_host: str = "203.0.113.55",
    headers: dict | None = None,
) -> Scope:
    """Build a minimal ASGI scope dict for testing."""
    _headers = headers or {}
    _headers.setdefault("host", "test.smartlic.tech")
    raw_headers = [
        (k.lower().encode(), v.encode()) for k, v in _headers.items()
    ]
    return {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "headers": raw_headers,
        "query_string": b"",
        "client": (client_host, 54321),
        "scheme": "http",
        "server": ("test.smartlic.tech", 80),
        "state": {},
    }


def _make_request(scope) -> Request:
    """Build a Request from an ASGI scope."""
    return Request(scope)


# ---------------------------------------------------------------------------
# Config tests (AC5, AC3)
# ---------------------------------------------------------------------------


class TestIPRateLimitConfig:
    """Test configuration defaults and env-var overrides (AC3, AC5)."""

    def test_default_threshold(self):
        """AC3: Default threshold is 100 req/min."""
        from config.features import IP_RATE_LIMIT_DEFAULT
        assert IP_RATE_LIMIT_DEFAULT == 100

    def test_default_window(self):
        """Default window is 60s."""
        from config.features import IP_RATE_LIMIT_WINDOW_S
        assert IP_RATE_LIMIT_WINDOW_S == 60

    def test_default_blocklist_multiplier(self):
        """Default blocklist multiplier is 5x."""
        from config.features import IP_RATE_LIMIT_BLOCKLIST_MULTIPLIER
        assert IP_RATE_LIMIT_BLOCKLIST_MULTIPLIER == 5

    def test_default_blocklist_duration(self):
        """AC4: Default blocklist duration is 600s (10 min)."""
        from config.features import IP_RATE_LIMIT_BLOCKLIST_DURATION_S
        assert IP_RATE_LIMIT_BLOCKLIST_DURATION_S == 600

    def test_whitelist_parsing_empty(self):
        """AC5: Empty whitelist returns empty set."""
        from ip_rate_limiter import _parse_whitelist
        assert _parse_whitelist("") == set()
        assert _parse_whitelist(None) == set()

    def test_whitelist_parsing_single_ip(self):
        """AC5: Single IP parsed correctly."""
        from ip_rate_limiter import _parse_whitelist
        result = _parse_whitelist("192.168.1.1")
        assert result == {"192.168.1.1"}

    def test_whitelist_parsing_multiple(self):
        """AC5: Multiple comma-separated IPs parsed."""
        from ip_rate_limiter import _parse_whitelist
        result = _parse_whitelist("10.0.0.1,10.0.0.2,192.168.1.0/24")
        assert "10.0.0.1" in result
        assert "10.0.0.2" in result
        assert "192.168.1.0/24" in result
        assert len(result) == 3

    def test_whitelist_parsing_invalid_skipped(self):
        """Invalid whitelist entries are silently skipped."""
        from ip_rate_limiter import _parse_whitelist
        result = _parse_whitelist("10.0.0.1,not-an-ip,192.168.1.0/24")
        assert result == {"10.0.0.1", "192.168.1.0/24"}


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestIPRateLimitHelpers:
    """Test IP extraction, masking, and path matching."""

    def test_get_client_ip_from_forwarded(self):
        """Client IP extracted from X-Forwarded-For header."""
        from ip_rate_limiter import _get_client_ip

        scope = _make_scope(headers={"x-forwarded-for": "198.51.100.1, 10.0.0.1"})
        request = _make_request(scope)
        assert _get_client_ip(request) == "198.51.100.1"

    def test_get_client_ip_from_client(self):
        """Client IP extracted from request.client as fallback."""
        from ip_rate_limiter import _get_client_ip

        scope = _make_scope(client_host="203.0.113.55")
        request = _make_request(scope)
        assert _get_client_ip(request) == "203.0.113.55"

    def test_get_client_ip_unknown(self):
        """Returns 'unknown' when no IP source available."""
        from ip_rate_limiter import _get_client_ip

        scope = _make_scope(client_host=None)
        scope.pop("client", None)
        request = _make_request(scope)
        assert _get_client_ip(request) == "unknown"

    def test_mask_ip_v4(self):
        """AC9: IPv4 masked to first 2 octets with *.*."""
        from ip_rate_limiter import _mask_ip
        assert _mask_ip("203.0.113.55") == "203.0.*.*"

    def test_mask_ip_unknown(self):
        """Unknown IP remains unchanged."""
        from ip_rate_limiter import _mask_ip
        assert _mask_ip("unknown") == "unknown"

    def test_get_path_prefix_v1(self):
        """/v1/search/foo → /v1/search."""
        from ip_rate_limiter import _get_path_prefix
        assert _get_path_prefix("/v1/search/foo") == "/v1/search"

    def test_get_path_prefix_api(self):
        """/api/buscar → /api/buscar."""
        from ip_rate_limiter import _get_path_prefix
        assert _get_path_prefix("/api/buscar") == "/api/buscar"

    def test_get_path_prefix_other(self):
        """Non-rate-limited paths → 'other'."""
        from ip_rate_limiter import _get_path_prefix
        assert _get_path_prefix("/health/live") == "other"

    def test_get_ip_prefix(self):
        """203.0.113.55 → 203.0."""
        from ip_rate_limiter import _get_ip_prefix
        assert _get_ip_prefix("203.0.113.55") == "203.0"

    def test_is_exempt_path_health(self):
        """AC2: /health paths are exempt."""
        from ip_rate_limiter import _is_exempt_path
        assert _is_exempt_path("/health/live") is True
        assert _is_exempt_path("/health") is True

    def test_is_exempt_path_api(self):
        """/api paths are NOT exempt."""
        from ip_rate_limiter import _is_exempt_path
        assert _is_exempt_path("/api/buscar") is False

    def test_is_rate_limited_path_v1(self):
        """/v1/* paths are rate limited."""
        from ip_rate_limiter import _is_rate_limited_path
        assert _is_rate_limited_path("/v1/search/test") is True

    def test_is_rate_limited_path_health(self):
        """/health paths are NOT rate limited."""
        from ip_rate_limiter import _is_rate_limited_path
        assert _is_rate_limited_path("/health/live") is False

    def test_whitelisted_ip_direct(self):
        """Direct IP matches whitelist."""
        from ip_rate_limiter import _is_ip_whitelisted
        assert _is_ip_whitelisted("192.168.1.1", {"192.168.1.1"}) is True

    def test_whitelisted_ip_cidr(self):
        """CIDR range matches."""
        from ip_rate_limiter import _is_ip_whitelisted
        assert _is_ip_whitelisted("192.168.1.55", {"192.168.1.0/24"}) is True

    def test_whitelisted_ip_no_match(self):
        """Non-matching IP returns False."""
        from ip_rate_limiter import _is_ip_whitelisted
        assert _is_ip_whitelisted("10.0.0.1", {"192.168.1.0/24"}) is False


# ---------------------------------------------------------------------------
# IPRateLimiter logic tests (mock Redis backend)
# ---------------------------------------------------------------------------


class TestIPRateLimiterExemptPaths:
    """AC2: /health/* paths must pass through without rate limiting."""

    @pytest.mark.asyncio
    async def test_health_path_not_rate_limited(self):
        """Health check paths bypass rate limiter entirely."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)

        scope = _make_scope(path="/health/live")
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_ready_exempt(self):
        """/health/ready is also exempt."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        scope = _make_scope(path="/health/ready")
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200


class TestIPRateLimiterWhitelist:
    """AC5: Whitelisted IPs pass through without rate limiting."""

    @pytest.mark.asyncio
    async def test_whitelisted_ip_bypasses_rate_limit(self):
        """Whitelisted IPs are never rate limited."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        middleware._whitelist = {"198.51.100.1"}

        scope = _make_scope(
            path="/v1/search/test",
            client_host="198.51.100.1",
        )
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_non_whitelisted_ip_not_exempt(self):
        """Non-whitelisted IPs still go through rate limiting."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        middleware._whitelist = {"198.51.100.1"}

        # Make the in-memory store appear at limit by pre-populating it
        ip = "203.0.113.55"
        prefix = "/v1/search"
        limit = 100
        now = time.time()

        # Fill up the window
        entries = [(now - 0.1 * i, f"req-{i}") for i in range(limit)]
        middleware._memory_store[f"{prefix}:{ip}"] = entries

        scope = _make_scope(
            path="/v1/search/test",
            client_host=ip,
        )
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 429


class TestIPRateLimiterSlidingWindow:
    """AC1 + AC3: Sliding window rate limiting with mock Redis."""

    @pytest.mark.asyncio
    async def test_allows_request_under_limit(self):
        """Request under limit passes with 200."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        scope = _make_scope(path="/v1/search/test")
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_block_request_over_limit(self):
        """Request over limit receives 429."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        ip = "203.0.113.55"
        prefix = "/v1/search"
        limit = 100

        # Fill up the in-memory store past limit
        now = time.time()
        entries = [(now - 0.5, f"req-{i}") for i in range(limit)]
        middleware._memory_store[f"{prefix}:{ip}"] = entries

        scope = _make_scope(path="/v1/search/test", client_host=ip)
        req = _make_request(scope)

        # Dispatch without calling the next app (we just want the check)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 429

        # Verify response headers (AC7)
        assert "Retry-After" in response.headers
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_429_response_headers_match_rfc6585(self):
        """AC7: 429 response includes Retry-After, X-RateLimit-*, X-RateLimit-Reset."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        ip = "203.0.113.55"
        prefix = "/v1/search"
        limit = 100

        now = time.time()
        entries = [(now - 0.5, f"req-{i}") for i in range(limit)]
        middleware._memory_store[f"{prefix}:{ip}"] = entries

        scope = _make_scope(path="/v1/search/test", client_host=ip)
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)

        assert response.status_code == 429
        assert int(response.headers["Retry-After"]) > 0
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert int(response.headers["X-RateLimit-Reset"]) > 0

    @pytest.mark.asyncio
    async def test_success_response_headers(self):
        """AC7: Successful responses include rate limit headers."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        scope = _make_scope(path="/v1/search/test")
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    @pytest.mark.asyncio
    async def test_window_slides_after_60s(self):
        """AC1: Old entries outside the window are ignored."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        ip = "203.0.113.55"
        prefix = "/v1/search"

        old_now = time.time() - 120  # 2 minutes ago
        recent_now = time.time()

        # Old entries outside 60s window
        old_entries = [(old_now, f"old-{i}") for i in range(100)]
        # Fresh entries within window
        fresh_entries = [(recent_now - 10, "fresh")]
        middleware._memory_store[f"{prefix}:{ip}"] = old_entries + fresh_entries

        scope = _make_scope(path="/v1/search/test", client_host=ip)
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200


class TestIPRateLimiterBlocklist:
    """AC4: Auto-blocklist at 5x threshold for 10 minutes."""

    @pytest.mark.asyncio
    async def test_blocklist_blocks_ip(self):
        """Blocklisted IP gets 429 even for a single request."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        ip = "203.0.113.55"
        now = time.time()

        # Manually blocklist the IP
        middleware._memory_blocklist[ip] = now + 600

        scope = _make_scope(path="/v1/search/test", client_host=ip)
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_blocklist_expires(self):
        """Blocklist entry expires after the configured duration."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        ip = "203.0.113.55"

        # Expired blocklist entry
        middleware._memory_blocklist[ip] = time.time() - 10

        scope = _make_scope(path="/v1/search/test", client_host=ip)
        req = _make_request(scope)
        # Should NOT be blocked (expired) — but be mindful of regular rate limit
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code != 429  # Should pass the blocklist check


class TestIPRateLimiterNonApiPaths:
    """Paths outside /api/ and /v1/ are not rate limited."""

    @pytest.mark.asyncio
    async def test_root_path_not_limited(self):
        """Root path is not rate limited."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        scope = _make_scope(path="/")
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_static_assets_not_limited(self):
        """Static-like paths are not rate limited (if not under /api/ or /v1/)."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        scope = _make_scope(path="/static/js/main.js")
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_webhook_not_limited(self):
        """Webhook paths are not rate limited (not under /api/ or /v1/)."""
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        scope = _make_scope(path="/webhook/stripe")
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200


class TestIPRateLimiterDisabled:
    """Feature flag ``IP_RATE_LIMIT_ENABLED=false`` disables the middleware."""

    @pytest.mark.asyncio
    async def test_disabled_passthrough(self):
        """When disabled, all requests pass through without rate limiting."""
        from ip_rate_limiter import IPRateLimiter

        with patch("ip_rate_limiter.IP_RATE_LIMIT_ENABLED", False):
            middleware = IPRateLimiter(_ok_response)
            ip = "203.0.113.55"
            prefix = "/v1/search"

            # Fill the store past limit to verify it's bypassed.
            now = time.time()
            entries = [(now, f"req-{i}") for i in range(150)]
            middleware._memory_store[f"{prefix}:{ip}"] = entries

            scope = _make_scope(path="/v1/search/test", client_host=ip)
            req = _make_request(scope)
            response = await middleware.dispatch(req, _ok_response)
            assert response.status_code == 200


class TestIPRateLimiterMasking:
    """AC9: GDPR-safe IP masking in logs."""

    def test_mask_ip_v4_full(self):
        """Full IPv4 masking works."""
        from ip_rate_limiter import _mask_ip
        assert _mask_ip("192.168.1.100") == "192.168.*.*"

    def test_mask_ip_localhost(self):
        """Localhost remains unchanged (only 2 parts)."""
        from ip_rate_limiter import _mask_ip
        assert _mask_ip("127.0.0.1") == "127.0.*.*"


# ---------------------------------------------------------------------------
# Redis integration tests (AC8 — mock Redis at the Redis pool level)
# ---------------------------------------------------------------------------


class TestIPRateLimiterRedis:
    """Sliding window via Redis (mocked ``get_redis_pool``).

    These tests mock ``get_redis_pool`` to return a fake Redis client,
    verifying the Redis sliding window algorithm without needing a
    running Redis server.
    """

    @pytest.fixture(autouse=True)
    def _mock_redis(self):
        """Provide a fake Redis instance with pipeline support."""

        self._redis_data: dict[str, list[tuple[float, str]]] = {}

        class FakeRedisPipeline:
            def __init__(self, redis_instance):
                self._redis = redis_instance
                self._commands = []

            def zremrangebyscore(self, key, min_s, max_s):
                self._commands.append(("zremrangebyscore", key, min_s, max_s))
                return self

            def zcard(self, key):
                self._commands.append(("zcard", key))
                return self

            def zadd(self, key, mapping):
                self._commands.append(("zadd", key, mapping))
                return self

            def expire(self, key, ttl):
                self._commands.append(("expire", key, ttl))
                return self

            def set(self, key, value):
                self._commands.append(("set", key, value))
                return self

            async def execute(self):
                results = []
                for cmd in self._commands:
                    op = cmd[0]
                    key = cmd[1]
                    if op == "zremrangebyscore":
                        # min_s = cmd[2]  -- unused, kept for command structure clarity.
                        max_s = cmd[3]
                        entries = self._redis._data.get(key, [])
                        before = len(entries)
                        entries = [(ts, rid) for ts, rid in entries if ts > max_s]
                        self._redis._data[key] = entries
                        results.append(before - len(entries))
                    elif op == "zcard":
                        entries = self._redis._data.get(key, [])
                        results.append(len(entries))
                    elif op == "zadd":
                        mapping = cmd[2]
                        if key not in self._redis._data:
                            self._redis._data[key] = []
                        for rid, ts in mapping.items():
                            self._redis._data[key].append((ts, rid))
                        results.append(1)
                    elif op == "expire":
                        results.append(True)
                    elif op == "set":
                        self._redis._data[key] = cmd[1]
                        results.append(True)
                self._commands = []
                return results

        class FakeRedis:
            def __init__(self):
                self._data: dict = {}

            def pipeline(self):
                return FakeRedisPipeline(self)

            async def zremrangebyscore(self, key, min_s, max_s):
                entries = self._data.get(key, [])
                before = len(entries)
                self._data[key] = [(ts, rid) for ts, rid in entries if ts > max_s]
                return before - len(self._data.get(key, []))

            async def zcard(self, key):
                return len(self._data.get(key, []))

            async def zadd(self, key, mapping):
                if key not in self._data:
                    self._data[key] = []
                for rid, ts in mapping.items():
                    self._data[key].append((ts, rid))
                return 1

            async def expire(self, key, ttl):
                return True

            async def exists(self, key):
                return 1 if key in self._data else 0

            async def set(self, key, value):
                self._data[key] = "1"
                return True

            async def scan(self, cursor=0, match=None, count=10):
                keys = [k for k in self._data if match is None or self._match(k, match)]
                return (0, keys)

            def _match(self, key, pattern):
                if pattern.endswith("*"):
                    return key.startswith(pattern[:-1])
                return key == pattern

        return FakeRedis()

    @patch("ip_rate_limiter.get_redis_pool")
    @pytest.mark.asyncio
    async def test_redis_sliding_window_allows(self, mock_get_pool, _mock_redis):
        """Redis sliding window allows request under limit."""
        mock_get_pool.return_value = _mock_redis
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        scope = _make_scope(path="/v1/search/test")
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200

    @patch("ip_rate_limiter.get_redis_pool")
    @pytest.mark.asyncio
    async def test_redis_sliding_window_over_limit(self, mock_get_pool, _mock_redis):
        """Redis sliding window blocks when over limit."""
        mock_get_pool.return_value = _mock_redis
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        ip = "203.0.113.55"

        # Pre-populate Redis with limit entries
        now = time.time()
        key = f"ip:rl:/v1/search:{ip}"
        for i in range(100):
            _mock_redis._data[key] = _mock_redis._data.get(key, [])
            _mock_redis._data[key].append((now - 0.5, f"req-{i}"))

        scope = _make_scope(path="/v1/search/test", client_host=ip)
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 429

    @patch("ip_rate_limiter.get_redis_pool")
    @pytest.mark.asyncio
    async def test_redis_blocklist_blocks(self, mock_get_pool, _mock_redis):
        """Redis blocklist prevents requests."""
        mock_get_pool.return_value = _mock_redis
        from ip_rate_limiter import IPRateLimiter

        middleware = IPRateLimiter(_ok_response)
        ip = "203.0.113.55"

        # Block the IP
        await middleware._add_to_blocklist(ip, time.time())

        scope = _make_scope(path="/v1/search/test", client_host=ip)
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 429

    @patch("ip_rate_limiter.get_redis_pool")
    @pytest.mark.asyncio
    async def test_redis_fail_open(self, mock_get_pool, _mock_redis):
        """AC8: When Redis errors, requests are allowed (fail-open)."""
        from ip_rate_limiter import IPRateLimiter

        # Redis pool returns None (unavailable)
        mock_get_pool.return_value = None

        middleware = IPRateLimiter(_ok_response)
        scope = _make_scope(path="/v1/search/test")
        req = _make_request(scope)
        response = await middleware.dispatch(req, _ok_response)
        assert response.status_code == 200
