"""Tests for 3-layer quota fallback (GAP-012 / #1590).

Tests:
  1. try_quota_fallback with Redis available — respects max daily limit.
  2. try_quota_fallback with Redis unavailable — fail open (Layer 3).
  3. try_quota_fallback counts correctly up to QUOTA_FALLBACK_MAX_DAILY.
  4. Integration with check_and_increment_quota_atomic on CircuitBreakerOpenError.
  5. QUOTA_FALLBACK_ACTIVE gauge is updated.

All tests mock the sync Redis client to avoid real Redis dependency.
IMPORTANT: Patches target the import-origin module, not the local namespace,
because quota_fallback uses lazy ``from redis_pool import get_sync_redis``.
"""

import importlib
import os

import pytest
from unittest.mock import MagicMock, patch


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_redis():
    """Return a MagicMock that behaves like a sync Redis client."""
    r = MagicMock()
    r.eval.return_value = 1
    return r


@pytest.fixture
def mock_redis_unavailable():
    """Patch redis_pool.get_sync_redis to return None (Redis offline)."""
    with patch("redis_pool.get_sync_redis", return_value=None):
        yield


@pytest.fixture
def mock_redis_available(mock_redis):
    """Patch redis_pool.get_sync_redis to return a working mock."""
    with patch("redis_pool.get_sync_redis", return_value=mock_redis):
        yield mock_redis


# ============================================================================
# Tests for try_quota_fallback (core function)
# ============================================================================


class TestTryQuotaFallback:
    """Direct tests for quota_fallback.try_quota_fallback()."""

    def test_redis_available_first_call_allowed(self, mock_redis_available):
        """First call should be allowed (INCR=1 <= 10)."""
        from quota.quota_fallback import try_quota_fallback

        result = try_quota_fallback("user-123")
        assert result is True

    def test_redis_available_under_limit(self, mock_redis_available):
        """Calls up to QUOTA_FALLBACK_MAX_DAILY should be allowed."""
        from quota.quota_fallback import try_quota_fallback, QUOTA_FALLBACK_MAX_DAILY

        for count in range(1, QUOTA_FALLBACK_MAX_DAILY + 1):
            mock_redis_available.eval.return_value = count
            result = try_quota_fallback("user-123")
            assert result is True, f"Call #{count} should be allowed"

    def test_redis_available_over_limit_blocked(self, mock_redis_available):
        """Call #11 should be blocked (exceeds QUOTA_FALLBACK_MAX_DAILY=10)."""
        from quota.quota_fallback import try_quota_fallback, QUOTA_FALLBACK_MAX_DAILY

        mock_redis_available.eval.return_value = QUOTA_FALLBACK_MAX_DAILY + 1
        result = try_quota_fallback("user-123")
        assert result is False

    def test_redis_unavailable_fail_open(self, mock_redis_unavailable):
        """When Redis is unavailable, Layer 3 fail-open should allow."""
        from quota.quota_fallback import try_quota_fallback

        result = try_quota_fallback("user-123")
        assert result is True  # Fail open

    def test_redis_eval_error_falls_to_layer3(self, mock_redis_available):
        """When Redis eval() raises, should fall through to Layer 3."""
        from quota.quota_fallback import try_quota_fallback

        mock_redis_available.eval.side_effect = RuntimeError("Redis connection lost")
        result = try_quota_fallback("user-123")
        assert result is True  # Fail open

    def test_redis_key_includes_user_id(self, mock_redis_available):
        """Redis key should follow the pattern quota:fallback:{user_id}."""
        from quota.quota_fallback import try_quota_fallback

        try_quota_fallback("test-user-xyz")
        call_args = mock_redis_available.eval.call_args
        assert call_args is not None
        # eval(script, num_keys, key, TTL)
        key_arg = call_args[0][2]
        assert "quota:fallback:" in key_arg
        assert "test-user-xyz" in key_arg

    def test_redis_ttl_set_in_eval(self, mock_redis_available):
        """The TTL should be passed as the fourth argument to eval."""
        from quota.quota_fallback import try_quota_fallback, QUOTA_FALLBACK_TTL

        try_quota_fallback("user-ttl-test")
        call_args = mock_redis_available.eval.call_args
        ttl_arg = call_args[0][3]
        assert ttl_arg == QUOTA_FALLBACK_TTL


# ============================================================================
# Tests for integration with check_and_increment_quota_atomic
# ============================================================================


class TestCheckAndIncrementQuotaIntegration:
    """Ensure the fallback is called when CircuitBreakerOpenError is raised."""

    def test_cb_open_calls_fallback_allowed(self):
        """CircuitBreakerOpenError should delegate to try_quota_fallback."""
        from supabase_client import CircuitBreakerOpenError
        from quota.quota_atomic import check_and_increment_quota_atomic

        with patch(
            "supabase_client.supabase_cb.call_sync",
            side_effect=CircuitBreakerOpenError("Supabase CB open"),
        ):
            with patch("redis_pool.get_sync_redis") as mock_get_redis:
                mock_redis = MagicMock()
                mock_redis.eval.return_value = 1
                mock_get_redis.return_value = mock_redis

                allowed, new_count, remaining = check_and_increment_quota_atomic(
                    "user-123", 100
                )
                assert allowed is True
                assert remaining == 100  # max_quota passed through

    def test_cb_open_calls_fallback_blocked(self):
        """When fallback limit is exceeded, CB open should block."""
        from supabase_client import CircuitBreakerOpenError
        from quota.quota_atomic import check_and_increment_quota_atomic
        from quota.quota_fallback import QUOTA_FALLBACK_MAX_DAILY

        with patch(
            "supabase_client.supabase_cb.call_sync",
            side_effect=CircuitBreakerOpenError("Supabase CB open"),
        ):
            with patch("redis_pool.get_sync_redis") as mock_get_redis:
                mock_redis = MagicMock()
                mock_redis.eval.return_value = QUOTA_FALLBACK_MAX_DAILY + 1
                mock_get_redis.return_value = mock_redis

                allowed, new_count, remaining = check_and_increment_quota_atomic(
                    "user-123", 100
                )
                assert allowed is False
                assert remaining == 0

    def test_cb_open_redis_unavailable_fail_open(self):
        """When both Supabase CB open AND Redis unavailable -> fail open."""
        from supabase_client import CircuitBreakerOpenError
        from quota.quota_atomic import check_and_increment_quota_atomic

        with patch(
            "supabase_client.supabase_cb.call_sync",
            side_effect=CircuitBreakerOpenError("Supabase CB open"),
        ):
            with patch("redis_pool.get_sync_redis", return_value=None):
                allowed, new_count, remaining = check_and_increment_quota_atomic(
                    "user-123", 100
                )
                assert allowed is True  # Layer 3 fail-open
                assert remaining == 100

    def test_generic_exception_calls_fallback_allowed(self):
        """Generic Exception in quota check should also use fallback."""
        from quota.quota_atomic import check_and_increment_quota_atomic

        with patch(
            "supabase_client.supabase_cb.call_sync",
            side_effect=RuntimeError("Supabase connection error"),
        ):
            with patch("redis_pool.get_sync_redis") as mock_get_redis:
                mock_redis = MagicMock()
                mock_redis.eval.return_value = 1
                mock_get_redis.return_value = mock_redis
                with patch(
                    "quota.quota_atomic.get_monthly_quota_used", return_value=0
                ):
                    with patch(
                        "quota.quota_atomic.increment_monthly_quota", return_value=1
                    ):
                        allowed, new_count, remaining = (
                            check_and_increment_quota_atomic("user-123", 100)
                        )
                        assert allowed is True

    def test_generic_exception_fallback_blocked(self):
        """Generic Exception + fallback exceeded should block."""
        from quota.quota_atomic import check_and_increment_quota_atomic
        from quota.quota_fallback import QUOTA_FALLBACK_MAX_DAILY

        with patch(
            "supabase_client.supabase_cb.call_sync",
            side_effect=RuntimeError("Supabase connection error"),
        ):
            with patch("redis_pool.get_sync_redis") as mock_get_redis:
                mock_redis = MagicMock()
                mock_redis.eval.return_value = QUOTA_FALLBACK_MAX_DAILY + 1
                mock_get_redis.return_value = mock_redis

                allowed, new_count, remaining = check_and_increment_quota_atomic(
                    "user-123", 100
                )
                assert allowed is False


# ============================================================================
# Tests for QUOTA_FALLBACK_ACTIVE gauge
# ============================================================================


class TestQuotaFallbackMetric:
    """QUOTA_FALLBACK_ACTIVE gauge updates correctly."""

    def test_metric_set_on_cb_open(self):
        """QUOTA_FALLBACK_ACTIVE should be set to 1 on CB open."""
        mock_gauge = MagicMock()
        from supabase_client import CircuitBreakerOpenError
        from quota.quota_atomic import check_and_increment_quota_atomic

        with patch(
            "supabase_client.supabase_cb.call_sync",
            side_effect=CircuitBreakerOpenError("Supabase CB open"),
        ):
            with patch("redis_pool.get_sync_redis", return_value=None):
                with patch(
                    "metrics.QUOTA_FALLBACK_ACTIVE", mock_gauge
                ):
                    check_and_increment_quota_atomic("user-metric", 100)
                    mock_gauge.set.assert_called_with(1)


# ============================================================================
# Tests for configuration defaults
# ============================================================================


class TestQuotaFallbackConfig:
    """Default env var configuration for quota fallback."""

    def test_default_max_daily(self):
        """QUOTA_FALLBACK_MAX_DAILY should default to 10."""
        from quota.quota_fallback import QUOTA_FALLBACK_MAX_DAILY

        assert QUOTA_FALLBACK_MAX_DAILY == 10

    def test_default_ttl(self):
        """QUOTA_FALLBACK_TTL should default to 86400 (24h)."""
        from quota.quota_fallback import QUOTA_FALLBACK_TTL

        assert QUOTA_FALLBACK_TTL == 86400

    @patch.dict(os.environ, {"QUOTA_FALLBACK_MAX_DAILY": "5"})
    def test_custom_max_daily(self):
        """QUOTA_FALLBACK_MAX_DAILY should be configurable via env var."""
        from quota import quota_fallback

        importlib.reload(quota_fallback)
        assert quota_fallback.QUOTA_FALLBACK_MAX_DAILY == 5

    @patch.dict(os.environ, {"QUOTA_FALLBACK_TTL": "43200"})
    def test_custom_ttl(self):
        """QUOTA_FALLBACK_TTL should be configurable via env var."""
        from quota import quota_fallback

        importlib.reload(quota_fallback)
        assert quota_fallback.QUOTA_FALLBACK_TTL == 43200
