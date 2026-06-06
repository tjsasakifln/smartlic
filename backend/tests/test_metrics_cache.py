"""Tests for FOUNDER-002: Redis cache for financial metrics.

Key mock patterns:
  - Supabase: patch("supabase_client.sb_execute") + patch("supabase_client.get_supabase")
    (because services.metrics_cache uses lazy imports inside function body)
  - Redis: patch("redis_pool.get_redis_pool") with AsyncMock
  - Cron services: patch("services.metrics_cache.compute_all_metrics") etc.
    (because services.metrics_cron also uses lazy imports inside function body)
"""

import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import date


# ============================================================================
# Shared test data
# ============================================================================

MOCK_MRR_DATA = [
    {"month": "2025-06-01", "mrr": 1000.0, "subscriber_count": 5},
    {"month": "2026-05-01", "mrr": 5000.0, "subscriber_count": 12},
    {"month": "2026-06-01", "mrr": 5200.0, "subscriber_count": 14},
]

MOCK_CHURN = 0.05  # 5%
MOCK_TTP30 = 0.12  # 12%
MOCK_TTP90 = 0.20  # 20%
MOCK_D7 = 0.65     # 65%
MOCK_ARPA = 397.0  # R$ 397

MOCK_METRICS = {
    "mrr_current": MOCK_MRR_DATA[-1],
    "churn_rate_30d": MOCK_CHURN,
    "trial_to_paid_30d": MOCK_TTP30,
    "trial_to_paid_90d": MOCK_TTP90,
    "d7_retention": MOCK_D7,
    "arpa": MOCK_ARPA,
}

# RPC calls are made in deterministic order: get_mrr, get_churn_rate_30d,
# get_trial_to_paid_30d, get_trial_to_paid_90d, get_d7_retention, get_arpa
_RPC_RESULTS_ORDER = [
    MOCK_MRR_DATA,     # get_mrr
    MOCK_CHURN,        # get_churn_rate_30d
    MOCK_TTP30,        # get_trial_to_paid_30d
    MOCK_TTP90,        # get_trial_to_paid_90d
    MOCK_D7,           # get_d7_retention
    MOCK_ARPA,         # get_arpa
]


def _make_rpc_result(data):
    """Create a mock sb_execute result with .data attribute."""
    return MagicMock(data=data)


def _build_rpc_side_effect(results=None):
    """Build a side_effect list for sb_execute that matches RPC call order.

    Each entry is a MagicMock with .data set to the result value.
    """
    if results is None:
        results = _RPC_RESULTS_ORDER
    return [_make_rpc_result(r) for r in results]


def _mock_pipeline(mock_redis):
    """Set up pipeline mock on an AsyncMock Redis client.

    redis-py async pipeline() is a synchronous call (returns a Pipeline
    object synchronously). Pipe methods like setex() are also sync.
    Only execute() is a coroutine.
    """
    pipe = MagicMock()
    pipe.setex = MagicMock(return_value=True)
    pipe.execute = AsyncMock()
    mock_redis.pipeline = MagicMock(return_value=pipe)
    return pipe


# ============================================================================
# Tests
# ============================================================================


class TestComputeAllMetrics:
    """Tests for compute_all_metrics()."""

    @pytest.mark.asyncio
    async def test_computes_all_metrics_successfully(self):
        """Should compute all 6 metrics from Supabase RPCs."""
        mock_sb = MagicMock()
        rpc_results = _build_rpc_side_effect()

        with patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("supabase_client.sb_execute", new_callable=AsyncMock, side_effect=rpc_results):

            from services.metrics_cache import compute_all_metrics
            results = await compute_all_metrics()

        assert "mrr_current" in results
        assert results["mrr_current"]["mrr"] == 5200.0
        assert results["mrr_current"]["subscriber_count"] == 14
        assert results["churn_rate_30d"] == MOCK_CHURN
        assert results["trial_to_paid_30d"] == MOCK_TTP30
        assert results["trial_to_paid_90d"] == MOCK_TTP90
        assert results["d7_retention"] == MOCK_D7
        assert results["arpa"] == MOCK_ARPA
        assert len(results) == 6

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_rpc_failure(self):
        """Should return zeros when all RPCs fail."""
        mock_sb = MagicMock()
        mock_sb_execute = AsyncMock(side_effect=Exception("Supabase down"))

        with patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("supabase_client.sb_execute", mock_sb_execute):

            from services.metrics_cache import compute_all_metrics
            results = await compute_all_metrics()

        assert results["mrr_current"]["mrr"] == 0
        assert results["mrr_current"]["subscriber_count"] == 0
        assert results["churn_rate_30d"] == 0.0
        assert results["trial_to_paid_30d"] == 0.0
        assert results["trial_to_paid_90d"] == 0.0
        assert results["d7_retention"] == 0.0
        assert results["arpa"] == 0.0

    @pytest.mark.asyncio
    async def test_empty_mrr_data_returns_placeholder(self):
        """Should use placeholder when MRR data is empty."""
        mock_sb = MagicMock()
        # First RPC (get_mrr) returns empty list; rest return None
        side_effects = [_make_rpc_result([])] + _build_rpc_side_effect([None] * 5)

        with patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("supabase_client.sb_execute", new_callable=AsyncMock, side_effect=side_effects):

            from services.metrics_cache import compute_all_metrics
            results = await compute_all_metrics()

        assert results["mrr_current"]["mrr"] == 0
        assert results["mrr_current"]["subscriber_count"] == 0
        assert results["mrr_current"]["month"] == date.today().isoformat()


class TestCacheMetrics:
    """Tests for cache_metrics()."""

    @pytest.mark.asyncio
    async def test_caches_all_metrics(self):
        """Should store all metrics in Redis with pipeline."""
        mock_redis = AsyncMock()
        pipe = _mock_pipeline(mock_redis)

        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
            from services.metrics_cache import cache_metrics
            await cache_metrics(MOCK_METRICS)

        # Should have called setex for each metric
        assert pipe.setex.call_count == 6
        for key in MOCK_METRICS:
            pipe.setex.assert_any_call(
                f"metrics:revenue:{key}", 3600, json.dumps(MOCK_METRICS[key], default=str)
            )
        # Pipeline should have been executed
        pipe.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_graceful_degradation_when_redis_unavailable(self):
        """Should not raise when Redis is unavailable."""
        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=None):
            from services.metrics_cache import cache_metrics
            # Should not raise
            await cache_metrics(MOCK_METRICS)

    @pytest.mark.asyncio
    async def test_graceful_degradation_on_redis_error(self):
        """Should not raise when Redis operations fail."""
        mock_redis = AsyncMock()
        mock_redis.pipeline.side_effect = Exception("Pipeline error")

        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
            from services.metrics_cache import cache_metrics
            # Should not raise
            await cache_metrics(MOCK_METRICS)


class TestGetCachedMetrics:
    """Tests for get_cached_metrics()."""

    @pytest.mark.asyncio
    async def test_cache_hit_returns_all_metrics(self):
        """Should return cached metrics without recomputing."""
        mock_redis = AsyncMock()
        cached_values = {f"metrics:revenue:{k}": json.dumps(v, default=str) for k, v in MOCK_METRICS.items()}

        async def mock_get(key):
            return cached_values.get(key)

        mock_redis.get = mock_get

        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
            from services.metrics_cache import get_cached_metrics
            results = await get_cached_metrics()

        assert results == MOCK_METRICS

    @pytest.mark.asyncio
    async def test_cache_miss_recomputes(self):
        """Should recompute when a cache key is missing."""
        mock_redis = AsyncMock()

        # Only return cached value for one metric, miss all others
        cached_mrr = json.dumps(MOCK_MRR_DATA[-1], default=str)
        cache = {"metrics:revenue:mrr_current": cached_mrr}

        async def mock_get(key):
            return cache.get(key)

        mock_redis.get = mock_get

        # Mock Supabase for recomputation
        mock_sb = MagicMock()
        rpc_results = _build_rpc_side_effect()
        pipe = _mock_pipeline(mock_redis)

        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis), \
             patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("supabase_client.sb_execute", new_callable=AsyncMock, side_effect=rpc_results):

            from services.metrics_cache import get_cached_metrics
            results = await get_cached_metrics()

        # Should have returned all metrics (recomputed + cached)
        assert len(results) == 6
        assert results["mrr_current"]["mrr"] == 5200.0
        assert results["churn_rate_30d"] == MOCK_CHURN

        # Should have re-cached (setex called after recomputation)
        assert pipe.setex.call_count >= 5  # At least 5 recomputed metrics cached

    @pytest.mark.asyncio
    async def test_computes_directly_when_redis_unavailable(self):
        """Should compute directly when Redis is unavailable."""
        mock_sb = MagicMock()
        # Only first RPC needs data; rest can be None since test checks MRR
        rpc_side = [_make_rpc_result(MOCK_MRR_DATA)] + _build_rpc_side_effect([None] * 5)

        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=None), \
             patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("supabase_client.sb_execute", new_callable=AsyncMock, side_effect=rpc_side):

            from services.metrics_cache import get_cached_metrics
            results = await get_cached_metrics()

        assert len(results) == 6
        assert results["mrr_current"]["mrr"] == 5200.0

    @pytest.mark.asyncio
    async def test_redis_exception_falls_back_to_compute(self):
        """Should compute directly when Redis raises an error."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))

        mock_sb = MagicMock()
        rpc_side = _build_rpc_side_effect([None] * 6)

        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis), \
             patch("supabase_client.get_supabase", return_value=mock_sb), \
             patch("supabase_client.sb_execute", new_callable=AsyncMock, side_effect=rpc_side):

            from services.metrics_cache import get_cached_metrics
            results = await get_cached_metrics()

        assert len(results) == 6  # Graceful degradation


class TestInvalidateMetricsCache:
    """Tests for invalidate_metrics_cache()."""

    @pytest.mark.asyncio
    async def test_invalidates_all_metric_keys(self):
        """Should delete all metrics:revenue:* keys."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[
            "metrics:revenue:mrr_current",
            "metrics:revenue:churn_rate_30d",
            "metrics:revenue:arpa",
        ])

        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
            from services.metrics_cache import invalidate_metrics_cache
            deleted = await invalidate_metrics_cache()

        assert deleted == 3
        mock_redis.keys.assert_awaited_once_with("metrics:revenue:*")
        mock_redis.delete.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_keys_returns_zero(self):
        """Should return 0 when no cache keys exist."""
        mock_redis = AsyncMock()
        mock_redis.keys = AsyncMock(return_value=[])

        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
            from services.metrics_cache import invalidate_metrics_cache
            deleted = await invalidate_metrics_cache()

        assert deleted == 0
        mock_redis.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_redis_unavailable_returns_zero(self):
        """Should return 0 when Redis is unavailable."""
        with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=None):
            from services.metrics_cache import invalidate_metrics_cache
            deleted = await invalidate_metrics_cache()

        assert deleted == 0


class TestMetricsCron:
    """Tests for metrics_cron.refresh_metrics_cache()."""

    @pytest.mark.asyncio
    async def test_refresh_metrics_cache(self):
        """Should compute and cache all metrics."""
        with patch("services.metrics_cache.compute_all_metrics", new_callable=AsyncMock, return_value=MOCK_METRICS), \
             patch("services.metrics_cache.cache_metrics", new_callable=AsyncMock) as mock_cache:

            from services.metrics_cron import refresh_metrics_cache
            result = await refresh_metrics_cache()

        assert result["status"] == "ok"
        assert result["metrics_count"] == 6
        mock_cache.assert_awaited_once_with(MOCK_METRICS)


class TestMetricsRefreshCronTask:
    """Tests for jobs.cron.metrics_refresh."""

    @pytest.mark.asyncio
    async def test_run_metrics_refresh_once_success(self):
        """Should run refresh and return status."""
        with patch("services.metrics_cron.refresh_metrics_cache",
                   new_callable=AsyncMock,
                   return_value={"status": "ok", "metrics_count": 6}):

            from jobs.cron.metrics_refresh import run_metrics_refresh_once
            result = await run_metrics_refresh_once()

        assert result["status"] == "ok"
        assert result["metrics_count"] == 6

    @pytest.mark.asyncio
    async def test_run_metrics_refresh_once_cb_error(self):
        """Should handle circuit breaker errors gracefully."""
        class CircuitBreakerError(Exception):
            pass

        with patch("services.metrics_cron.refresh_metrics_cache",
                   new_callable=AsyncMock,
                   side_effect=CircuitBreakerError("CircuitBreaker is OPEN")):

            from jobs.cron.metrics_refresh import run_metrics_refresh_once
            result = await run_metrics_refresh_once()

        assert result["status"] == "skipped"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_run_metrics_refresh_once_generic_error(self):
        """Should handle generic errors gracefully."""
        with patch("services.metrics_cron.refresh_metrics_cache",
                   new_callable=AsyncMock,
                   side_effect=Exception("Generic error")):

            from jobs.cron.metrics_refresh import run_metrics_refresh_once
            result = await run_metrics_refresh_once()

        assert result["status"] == "error"
        assert "error" in result

    @pytest.mark.asyncio
    async def test_start_metrics_refresh_task_returns_task(self):
        """Should create and return an asyncio Task."""
        from jobs.cron.metrics_refresh import start_metrics_refresh_task
        task = await start_metrics_refresh_task()

        assert task is not None
        assert task.get_name() == "metrics_refresh"
        # Cancel to clean up
        task.cancel()

    def test_registered_in_scheduler(self):
        """Should be registered in the centralised cron scheduler."""
        from jobs.cron.scheduler import register_all_cron_tasks
        tasks = register_all_cron_tasks()
        names = [t.__name__ for t in tasks]

        assert "start_metrics_refresh_task" in names


class TestMetricsConstants:
    """Tests for module-level constants."""

    def test_metrics_ttl_is_one_hour(self):
        from services.metrics_cache import METRICS_TTL
        assert METRICS_TTL == 3600

    def test_metrics_prefix(self):
        from services.metrics_cache import METRICS_PREFIX
        assert METRICS_PREFIX == "metrics:revenue"

    def test_metrics_list_has_six_items(self):
        from services.metrics_cache import METRICS
        assert len(METRICS) == 6
        assert "mrr_current" in METRICS
        assert "churn_rate_30d" in METRICS
        assert "trial_to_paid_30d" in METRICS
        assert "trial_to_paid_90d" in METRICS
        assert "d7_retention" in METRICS
        assert "arpa" in METRICS
