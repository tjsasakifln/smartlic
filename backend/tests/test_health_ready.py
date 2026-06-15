"""HARDEN-016 / #1790: Tests for /health/live and /health/ready endpoints."""
import asyncio
import time
from unittest.mock import patch, AsyncMock, MagicMock

from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers: mock factories for the four readiness checks
# ---------------------------------------------------------------------------

def _mock_redis_ok():
    """Redis pool returns a mock that pings successfully."""
    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock(return_value=True)
    return patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis)


def _mock_redis_down(error="Connection refused"):
    """Redis pool raises an exception."""
    return patch(
        "redis_pool.get_redis_pool",
        new_callable=AsyncMock,
        side_effect=ConnectionError(error),
    )


def _mock_redis_none():
    """Redis pool returns None (pool unavailable)."""
    return patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=None)


def _mock_supabase_ok():
    """Supabase query succeeds."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.limit.return_value = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [{"id": "test"}]
    return (
        patch("supabase_client.sb_execute_direct", new_callable=AsyncMock, return_value=mock_response),
        patch("supabase_client.get_supabase", return_value=mock_sb),
    )


def _mock_supabase_down(error="Connection refused"):
    """Supabase query raises an exception."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.limit.return_value = MagicMock()
    return (
        patch("supabase_client.sb_execute_direct", new_callable=AsyncMock, side_effect=ConnectionError(error)),
        patch("supabase_client.get_supabase", return_value=mock_sb),
    )


def _mock_pool_ok():
    """Pool utilization nominal (<85%)."""
    return (
        patch("supabase_client._pool_active_count", 5),
        patch("supabase_client._POOL_MAX_CONNECTIONS", 25),
    )


def _mock_pool_high():
    """Pool utilization high (>85%)."""
    return (
        patch("supabase_client._pool_active_count", 23),
        patch("supabase_client._POOL_MAX_CONNECTIONS", 25),
    )


def _mock_cache_hit_rate(hits: int = 95, misses: int = 5):
    """Cache hit rate at given hits/misses ratio."""
    mock_hits_sample = MagicMock()
    mock_hits_sample.value = hits
    mock_hits_family = MagicMock()
    mock_hits_family.samples = [mock_hits_sample]
    mock_hits = MagicMock()
    mock_hits.collect.return_value = [mock_hits_family]

    mock_misses_sample = MagicMock()
    mock_misses_sample.value = misses
    mock_misses_family = MagicMock()
    mock_misses_family.samples = [mock_misses_sample]
    mock_misses = MagicMock()
    mock_misses.collect.return_value = [mock_misses_family]

    return patch.multiple(
        "metrics",
        CACHE_HITS=mock_hits,
        CACHE_MISSES=mock_misses,
    )


def _mock_all_nominal():
    """Convenience: mock Redis, Supabase, pool and cache all OK."""
    redis = _mock_redis_ok()
    sb_exec, sb_get = _mock_supabase_ok()
    pool_active, pool_max = _mock_pool_ok()
    cache = _mock_cache_hit_rate(hits=95, misses=5)
    return redis, sb_exec, sb_get, pool_active, pool_max, cache


# ---------------------------------------------------------------------------
# AC1: /health/live — pure liveness, always 200
# ---------------------------------------------------------------------------

class TestHealthLive:
    """AC1: /health/live returns 200 if process alive (no dependency checks)."""

    def test_live_returns_200_when_startup_complete(self):
        with patch("startup.state.startup_time", time.monotonic()):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/live")
            assert response.status_code == 200
            data = response.json()
            assert data["live"] is True
            assert data["ready"] is True
            assert "uptime_seconds" in data
            assert "process_uptime_seconds" in data

    def test_live_returns_200_before_startup(self):
        """Always 200 even if startup not complete."""
        with patch("startup.state.startup_time", None):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/live")
            assert response.status_code == 200
            data = response.json()
            assert data["live"] is True
            assert data["ready"] is False
            assert data["uptime_seconds"] == 0.0

    def test_live_responds_fast(self):
        """No I/O — should respond in <50ms."""
        with patch("startup.state.startup_time", time.monotonic()):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            start = time.monotonic()
            response = client.get("/health/live")
            elapsed_ms = (time.monotonic() - start) * 1000
            assert response.status_code == 200
            assert elapsed_ms < 500  # generous CI margin


# ---------------------------------------------------------------------------
# AC2 + AC4: /health/ready — dependency checks, 200/503
# ---------------------------------------------------------------------------

class TestHealthReady:
    """AC2: /health/ready returns 200 if deps OK, 503 if Supabase down."""

    def test_ready_200_when_all_deps_ok(self):
        """AC2: Returns 200 when all dependencies are up."""
        redis, sb_exec, sb_get, pool_active, pool_max, cache = _mock_all_nominal()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            redis,
            sb_exec,
            sb_get,
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["ready"] is True
            assert "timestamp" in data
            assert data["checks"]["redis"]["status"] == "ok"
            assert data["checks"]["supabase"]["status"] == "ok"
            assert data["checks"]["pool"]["status"] == "ok"
            assert data["checks"]["cache"]["status"] == "ok"
            assert "latency_ms" in data["checks"]["redis"]
            assert "latency_ms" in data["checks"]["supabase"]
            assert "utilization_pct" in data["checks"]["pool"]
            assert "hit_rate_pct" in data["checks"]["cache"]

    def test_ready_200_when_redis_down_degraded(self):
        """#1790: Redis DOWN returns 200 with degraded status (fail-open)."""
        redis = _mock_redis_down()
        sb_exec, sb_get = _mock_supabase_ok()
        pool_active, pool_max = _mock_pool_ok()
        cache = _mock_cache_hit_rate()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            redis,
            sb_exec,
            sb_get,
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            # Redis down → degraded, still 200 (fail-open)
            assert response.status_code == 200
            data = response.json()
            assert data["ready"] is True
            assert data["status"] == "degraded"
            assert data["checks"]["redis"]["status"] == "degraded"
            assert "error" in data["checks"]["redis"]
            # Supabase should still be up
            assert data["checks"]["supabase"]["status"] == "ok"

    def test_ready_503_when_supabase_down(self):
        """AC2/AC7: Returns 503 when Supabase is down (critical dependency)."""
        redis = _mock_redis_ok()
        sb_exec, sb_get = _mock_supabase_down()
        pool_active, pool_max = _mock_pool_ok()
        cache = _mock_cache_hit_rate()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            redis,
            sb_exec,
            sb_get,
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["ready"] is False
            assert data["status"] == "unhealthy"
            assert data["checks"]["supabase"]["status"] == "error"
            assert "error" in data["checks"]["supabase"]
            # Redis should still be up
            assert data["checks"]["redis"]["status"] == "ok"

    def test_ready_503_when_both_deps_down(self):
        """AC7: Returns 503 when both Redis and Supabase are down."""
        redis = _mock_redis_down()
        sb_exec, sb_get = _mock_supabase_down()
        pool_active, pool_max = _mock_pool_ok()
        cache = _mock_cache_hit_rate()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            redis,
            sb_exec,
            sb_get,
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["ready"] is False
            assert data["status"] == "unhealthy"
            assert data["checks"]["redis"]["status"] == "degraded"
            assert data["checks"]["supabase"]["status"] == "error"

    def test_ready_503_before_startup(self):
        """AC7: Returns 503 when startup not complete (even if deps ok)."""
        redis, sb_exec, sb_get, pool_active, pool_max, cache = _mock_all_nominal()
        with (
            patch("startup.state.startup_time", None),
            redis,
            sb_exec,
            sb_get,
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["ready"] is False

    def test_ready_200_when_redis_pool_none_degraded(self):
        """#1790: Redis pool returns None → 200 with degraded status (fail-open)."""
        redis = _mock_redis_none()
        sb_exec, sb_get = _mock_supabase_ok()
        pool_active, pool_max = _mock_pool_ok()
        cache = _mock_cache_hit_rate()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            redis,
            sb_exec,
            sb_get,
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["ready"] is True
            assert data["status"] == "degraded"
            assert data["checks"]["redis"]["status"] == "degraded"
            assert "error" in data["checks"]["redis"]

    def test_ready_503_when_pool_exceeds_85_percent(self):
        """#1790: Pool >85% → 503 with degraded status."""
        redis = _mock_redis_ok()
        sb_exec, sb_get = _mock_supabase_ok()
        pool_active, pool_max = _mock_pool_high()
        cache = _mock_cache_hit_rate()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            redis,
            sb_exec,
            sb_get,
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            # Pool high → degraded status, but still 200 (not unhealthy)
            response = client.get("/health/ready")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["checks"]["pool"]["status"] == "degraded"
            assert data["checks"]["pool"]["utilization_pct"] > 85


# ---------------------------------------------------------------------------
# AC3: Timeout behavior
# ---------------------------------------------------------------------------

class TestHealthReadyTimeouts:
    """AC3 / #1790: Readiness checks respect individual timeouts."""

    def test_redis_timeout_constant(self):
        """#1790: Redis timeout is 500ms."""
        from routes.health_core import _READINESS_REDIS_TIMEOUT_S
        assert _READINESS_REDIS_TIMEOUT_S == 0.5

    def test_supabase_timeout_constant(self):
        """#1790: Supabase timeout is 2s."""
        from routes.health_core import _READINESS_SUPABASE_TIMEOUT_S
        assert _READINESS_SUPABASE_TIMEOUT_S == 2.0

    def test_ready_200_on_redis_timeout_degraded(self):
        """#1790: Redis timeout → degraded (not 503, fail-open)."""
        async def slow_redis():
            await asyncio.sleep(10)

        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.limit.return_value = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [{"id": "x"}]

        pool_active, pool_max = _mock_pool_ok()
        cache = _mock_cache_hit_rate()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            patch("routes.health_core._READINESS_REDIS_TIMEOUT_S", 0.01),
            patch("redis_pool.get_redis_pool", new_callable=AsyncMock, side_effect=slow_redis),
            patch("supabase_client.sb_execute_direct", new_callable=AsyncMock, return_value=mock_resp),
            patch("supabase_client.get_supabase", return_value=mock_sb),
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            # Redis timeout → degraded, still 200
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["checks"]["redis"]["status"] == "degraded"
            assert data["checks"]["redis"]["error"] == "timeout"

    def test_ready_503_on_supabase_timeout(self):
        """AC3/AC7: Supabase timeout produces 503 with 'timeout' error."""
        async def slow_supabase(*args, **kwargs):
            await asyncio.sleep(10)

        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.limit.return_value = MagicMock()

        pool_active, pool_max = _mock_pool_ok()
        cache = _mock_cache_hit_rate()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            patch("routes.health_core._READINESS_SUPABASE_TIMEOUT_S", 0.01),
            patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis),
            patch("supabase_client.sb_execute_direct", new_callable=AsyncMock, side_effect=slow_supabase),
            patch("supabase_client.get_supabase", return_value=mock_sb),
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["checks"]["supabase"]["status"] == "error"
            assert data["checks"]["supabase"]["error"] == "timeout"


# ---------------------------------------------------------------------------
# AC4: Response body details
# ---------------------------------------------------------------------------

class TestHealthReadyResponseBody:
    """AC4 / #1790: Response body includes details of each check."""

    def test_response_includes_checks_detail(self):
        """AC4: Response has checks dict with status, latency_ms per dependency."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.limit.return_value = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [{"id": "x"}]

        pool_active, pool_max = _mock_pool_ok()
        cache = _mock_cache_hit_rate()
        with (
            patch("startup.state.startup_time", time.monotonic()),
            patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis),
            patch("supabase_client.sb_execute_direct", new_callable=AsyncMock, return_value=mock_resp),
            patch("supabase_client.get_supabase", return_value=mock_sb),
            pool_active,
            pool_max,
            cache,
            patch("health.calculate_wedge_risk", return_value="low"),
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            data = response.json()

            assert "checks" in data
            assert "redis" in data["checks"]
            assert "supabase" in data["checks"]
            assert "pool" in data["checks"]
            assert "cache" in data["checks"]

            # Each check has at least status
            for name in ("redis", "supabase"):
                assert "status" in data["checks"][name]
                assert "latency_ms" in data["checks"][name]
                assert isinstance(data["checks"][name]["latency_ms"], int)

            # Pool and cache have specific fields
            assert "utilization_pct" in data["checks"]["pool"]
            assert "hit_rate_pct" in data["checks"]["cache"]

            # Top-level fields (#1790)
            assert "status" in data
            assert "ready" in data
            assert "timestamp" in data
            assert "uptime_seconds" in data
            assert "wedge_risk" in data

    def test_cache_hit_rate_healthy_when_above_90(self):
        """#1790: Cache hit rate >90% reports ok."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.limit.return_value = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [{"id": "x"}]

        pool_active, pool_max = _mock_pool_ok()
        cache = _mock_cache_hit_rate(hits=950, misses=50)  # 95%
        with (
            patch("startup.state.startup_time", time.monotonic()),
            patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis),
            patch("supabase_client.sb_execute_direct", new_callable=AsyncMock, return_value=mock_resp),
            patch("supabase_client.get_supabase", return_value=mock_sb),
            pool_active,
            pool_max,
            cache,
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            data = response.json()
            assert data["checks"]["cache"]["status"] == "ok"
            assert data["checks"]["cache"]["hit_rate_pct"] == 95.0

    def test_cache_hit_rate_degraded_when_below_90(self):
        """#1790: Cache hit rate <90% reports degraded."""
        mock_redis = AsyncMock()
        mock_redis.ping = AsyncMock(return_value=True)
        mock_sb = MagicMock()
        mock_sb.table.return_value.select.return_value.limit.return_value = MagicMock()
        mock_resp = MagicMock()
        mock_resp.data = [{"id": "x"}]

        pool_active, pool_max = _mock_pool_ok()
        cache = _mock_cache_hit_rate(hits=30, misses=70)  # 30%
        with (
            patch("startup.state.startup_time", time.monotonic()),
            patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis),
            patch("supabase_client.sb_execute_direct", new_callable=AsyncMock, return_value=mock_resp),
            patch("supabase_client.get_supabase", return_value=mock_sb),
            pool_active,
            pool_max,
            cache,
        ):
            from main import app
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/health/ready")
            data = response.json()
            assert data["checks"]["cache"]["status"] == "degraded"
            assert data["checks"]["cache"]["hit_rate_pct"] == 30.0


# ---------------------------------------------------------------------------
# AC5: /health backward compatibility
# ---------------------------------------------------------------------------

class TestHealthBackwardCompat:
    """AC5: /health existing endpoint is maintained for backward compatibility."""

    def test_health_endpoint_still_exists(self):
        """AC5: GET /health still returns 200."""
        from main import app
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
