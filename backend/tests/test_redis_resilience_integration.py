"""Integration test: Redis offline -> sistema degradado em todos os modulos.

#1881: Verifica que cada modulo que consome Redis continua operando (degradado)
quando Redis esta indisponivel, sem crashar.

Estrategia:
  1. Patch ``redis_pool.get_redis_pool`` / ``get_sync_redis`` para retornar None
     (simula Redis DOWN).
  2. Para cada modulo, executa a operacao Redis e verifica que retorna fallback
     sem exception.
  3. Verifica metricas ``smartlic_redis_fallback_total`` foram incrementadas.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _disable_metrics():
    """Disable Prometheus metrics for test isolation."""
    with patch("metrics._PROMETHEUS_AVAILABLE", False):
        yield


@pytest.fixture
def mock_redis_down():
    """Simulate Redis DOWN: all pool functions return None.

    Yields a list that accumulates (module, method) tuples for each
    safe_redis_call fallback that would be recorded.
    """
    # Make get_redis_pool (async) return None
    pool_patcher = patch("redis_pool.get_redis_pool", return_value=None)
    # Make get_sync_redis (sync) return None
    sync_patcher = patch("redis_pool.get_sync_redis", return_value=None)
    # Make get_sse_redis_pool (async) return None
    sse_patcher = patch("redis_pool.get_sse_redis_pool", return_value=None)
    # Make is_redis_available return False
    avail_patcher = patch("redis_pool.is_redis_available", return_value=False)
    # Ensure get_fallback_cache returns a working MagicMock
    from redis_pool import InMemoryCache
    fallback_cache = InMemoryCache()
    fallback_patcher = patch("redis_pool.get_fallback_cache", return_value=fallback_cache)

    pool_patcher.start()
    sync_patcher.start()
    sse_patcher.start()
    avail_patcher.start()
    fallback_patcher.start()
    yield
    pool_patcher.stop()
    sync_patcher.stop()
    sse_patcher.stop()
    avail_patcher.stop()
    fallback_patcher.stop()


# ===================================================================
# Module-level tests: each module degrades gracefully when Redis is DOWN
# ===================================================================


@pytest.mark.asyncio
async def test_rate_limiter_degraded(mock_redis_down):
    """rate_limiter.RateLimiter: Redis DOWN -> in-memory fallback."""
    from rate_limiter import RateLimiter

    limiter = RateLimiter()
    allowed, retry_after = await limiter.check_rate_limit("test_user", 10)

    # Must allow (fail-open with in-memory fallback)
    assert allowed is True
    assert retry_after == 0


@pytest.mark.asyncio
async def test_flexible_rate_limiter_degraded(mock_redis_down):
    """rate_limiter.FlexibleRateLimiter: Redis DOWN -> in-memory fallback."""
    from rate_limiter import _flexible_limiter

    allowed, retry_after, remaining = await _flexible_limiter.check_rate_limit(
        "test:key:user1", 10, 60
    )

    assert allowed is True
    assert retry_after == 0
    assert remaining == 9


@pytest.mark.asyncio
async def test_pncp_rate_limiter_degraded(mock_redis_down):
    """rate_limiter.RedisRateLimiter (pncp): Redis DOWN -> fail-open."""
    from rate_limiter import pncp_rate_limiter

    acquired = await pncp_rate_limiter.acquire(timeout=1.0)
    assert acquired is True  # Fail-open


@pytest.mark.asyncio
async def test_rate_limiter_stats_degraded(mock_redis_down):
    """rate_limiter.RedisRateLimiter.get_stats: Redis DOWN -> local backend."""
    from rate_limiter import pcp_rate_limiter

    stats = await pcp_rate_limiter.get_stats()
    assert stats["backend"] == "local"


@pytest.mark.asyncio
async def test_sse_xread_degraded(mock_redis_down):
    """routes/search_sse: Redis Streams xread -> safe_redis_call retorna [].

    Simula o fluxo de SSE quando _redis.xread eh chamado e retorna fallback [].
    O loop continua no ramo 'no new data' sem crashar.
    """
    # We test safe_redis_call directly since xread is inside a long-running generator
    from redis_resilience import safe_redis_call

    # Simulate what happens when _redis is None (controlled by mock_redis_down -> get_sse_redis_pool returns None)
    # The main SSE code would have set _use_streams = False when _redis is None,
    # so xread wouldn't be called at all.
    # The fallback path is tested: safe_redis_call returning [] for xread
    result = await safe_redis_call(
        # We can't easily create a real coroutine here since redis is None,
        # so we test safe_redis_call's fallback behavior directly
        AsyncMock(side_effect=ConnectionError("Redis DOWN"))(),
        fallback=[],
        method_name="xread",
        module="sse",
    )
    assert result == []


@pytest.mark.asyncio
async def test_cache_swr_is_revalidating_degraded(mock_redis_down):
    """cache.swr._is_revalidating: Redis DOWN -> returns False."""
    from cache.swr import _is_revalidating

    result = await _is_revalidating("test_hash_123")
    assert result is False


@pytest.mark.asyncio
async def test_cache_swr_mark_revalidating_degraded(mock_redis_down):
    """cache.swr._mark_revalidating: Redis DOWN -> falls to InMemoryCache."""
    from cache.swr import _mark_revalidating

    # Should succeed with InMemoryCache fallback
    result = await _mark_revalidating("test_hash_456", 60)
    assert result is True


@pytest.mark.asyncio
async def test_cache_swr_clear_revalidating_degraded(mock_redis_down):
    """cache.swr._clear_revalidating: Redis DOWN -> falls to InMemoryCache."""
    from cache.swr import _clear_revalidating

    # Should not raise
    await _clear_revalidating("test_hash_789")


@pytest.mark.asyncio
async def test_feature_flags_get_override_degraded(mock_redis_down):
    """routes/feature_flags._redis_get_override: Redis DOWN -> returns None."""
    from routes.feature_flags import _redis_get_override

    result = await _redis_get_override("TEST_FLAG")
    assert result is None


@pytest.mark.asyncio
async def test_feature_flags_set_override_degraded(mock_redis_down):
    """routes/feature_flags._redis_set_override: Redis DOWN -> returns False."""
    from routes.feature_flags import _redis_set_override

    result = await _redis_set_override("TEST_FLAG", True)
    assert result is False


@pytest.mark.asyncio
async def test_feature_flags_delete_override_degraded(mock_redis_down):
    """routes/feature_flags._redis_delete_override: Redis DOWN -> no-op."""
    from routes.feature_flags import _redis_delete_override

    # Should not raise
    await _redis_delete_override("TEST_FLAG")


@pytest.mark.asyncio
async def test_feature_flags_clear_all_overrides_degraded(mock_redis_down):
    """routes/feature_flags._redis_clear_all_overrides: Redis DOWN -> returns 0."""
    from routes.feature_flags import _redis_clear_all_overrides

    count = await _redis_clear_all_overrides()
    assert count == 0


# ===================================================================
# Cache.redis (sync) tests
# ===================================================================


def test_cache_redis_save_degraded(mock_redis_down):
    """cache.redis._save_to_redis: Redis DOWN -> fallback to InMemoryCache."""
    from cache.redis import _save_to_redis
    from cache.enums import CachePriority

    # Should not raise - falls through to InMemoryCache
    _save_to_redis(
        "test_cache_key",
        [{"id": 1, "title": "test"}],
        ["PNCP"],
        priority=CachePriority.HOT,
    )


def test_cache_redis_get_degraded(mock_redis_down):
    """cache.redis._get_from_redis: Redis DOWN -> fallback returns None."""
    from cache.redis import _get_from_redis

    result = _get_from_redis("nonexistent_key")
    assert result is None


# ===================================================================
# Quota fallback (sync Redis) tests
# ===================================================================


def test_quota_fallback_degraded(mock_redis_down):
    """quota.quota_fallback.try_quota_fallback: Redis DOWN -> Layer 3 fail-open."""
    from quota.quota_fallback import try_quota_fallback

    # When both Supabase and Redis are down, Layer 3 fails open = True
    result = try_quota_fallback("test_user_id")
    assert result is True


# ===================================================================
# safe_redis_call direct tests
# ===================================================================


@pytest.mark.asyncio
async def test_safe_redis_call_timeout():
    """safe_redis_call: TimeoutError -> returns fallback."""
    from redis_resilience import safe_redis_call

    async def _slow_op():
        import asyncio
        await asyncio.sleep(10)
        return "done"

    result = await safe_redis_call(
        _slow_op(),
        fallback="fallback_value",
        timeout_s=0.01,
        method_name="test_op",
        module="test_module",
    )
    assert result == "fallback_value"


@pytest.mark.asyncio
async def test_safe_redis_call_connection_error():
    """safe_redis_call: ConnectionError -> returns fallback."""
    from redis_resilience import safe_redis_call

    async def _failing_op():
        raise ConnectionError("Connection refused")

    result = await safe_redis_call(
        _failing_op(),
        fallback=42,
        method_name="test_op",
        module="test_module",
    )
    assert result == 42


@pytest.mark.asyncio
async def test_safe_redis_call_unexpected_error():
    """safe_redis_call: Unexpected error -> returns fallback."""
    from redis_resilience import safe_redis_call

    async def _crash_op():
        raise RuntimeError("Something unexpected")

    result = await safe_redis_call(
        _crash_op(),
        fallback=[],
        method_name="test_op",
        module="test_module",
    )
    assert result == []


@pytest.mark.asyncio
async def test_safe_redis_call_success():
    """safe_redis_call: Success -> returns actual result."""
    from redis_resilience import safe_redis_call

    async def _success_op():
        return "real_data"

    result = await safe_redis_call(
        _success_op(),
        fallback="fallback",
        method_name="test_op",
        module="test_module",
    )
    assert result == "real_data"


@pytest.mark.asyncio
async def test_safe_redis_call_inferred_fallback():
    """safe_redis_call: Fallback inferido do method_name."""
    from redis_resilience import safe_redis_call

    async def _failing_op():
        raise ConnectionError("DOWN")

    # get fallback -> None
    result = await safe_redis_call(
        _failing_op(),
        method_name="get",
        module="test_module",
    )
    assert result is None

    # exists fallback -> False
    result = await safe_redis_call(
        _failing_op(),
        method_name="exists",
        module="test_module",
    )
    assert result is False

    # incr fallback -> 1
    result = await safe_redis_call(
        _failing_op(),
        method_name="incr",
        module="test_module",
    )
    assert result == 1


# ===================================================================
# Metric counter tests
# ===================================================================


@pytest.mark.asyncio
async def test_safe_redis_call_tracks_metrics():
    """safe_redis_call: Fallback incrementa contador Prometheus."""
    # Enable metrics for this test
    from metrics import REDIS_FALLBACK_TOTAL

    with patch("metrics._PROMETHEUS_AVAILABLE", True), \
         patch("metrics.METRICS_ENABLED", True):
        from redis_resilience import safe_redis_call

        async def _failing_op():
            raise ConnectionError("DOWN")

        with patch.object(REDIS_FALLBACK_TOTAL, "labels") as mock_labels:
            mock_labels.return_value.inc = MagicMock()

            await safe_redis_call(
                _failing_op(),
                fallback=None,
                method_name="get",
                module="rate_limiter",
            )

            mock_labels.assert_called_once_with(
                module="rate_limiter", method="get", reason="connection_error",
            )
            mock_labels.return_value.inc.assert_called_once()


# ===================================================================
# ResilientRedis tests
# ===================================================================


@pytest.mark.asyncio
async def test_resilient_redis_dead_method():
    """ResilientRedis: Redis None -> all methods return safe defaults."""
    from redis_resilience import ResilientRedis

    safe = ResilientRedis(None)
    assert safe.is_alive() is False

    # Read returns None
    result = await safe.get("key")
    assert result is None

    # exists returns False
    result = await safe.exists("key")
    assert result is False

    # incr returns 1
    result = await safe.incr("key")
    assert result == 1

    # set returns True
    result = await safe.set("key", "value")
    assert result is True

    # delete returns 0
    result = await safe.delete("key")
    assert result == 0

    # scan returns empty cursor + list
    result = await safe.scan()
    assert result == (0, [])


@pytest.mark.asyncio
async def test_resilient_redis_alive_calls_real_redis(mock_redis_down):
    """ResilientRedis: With real Redis -> safe_redis_call wraps each call.

    When the underlying client is real and Redis goes down mid-operation,
    safe_redis_call handles the fallback.
    """
    from redis_resilience import ResilientRedis

    # Create a mock redis whose get() returns a coroutine that raises ConnectionError
    mock_redis = MagicMock()

    async def _failing_get(*args, **kwargs):
        raise ConnectionError("DOWN")

    mock_redis.get = MagicMock(side_effect=_failing_get)

    safe = ResilientRedis(mock_redis)
    assert safe.is_alive() is True

    result = await safe.get("key")
    assert result is None  # safe_redis_call fallback for get
