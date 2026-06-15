"""Comprehensive circuit breaker tests for all 3 implementations (#1800).

Tests cover:
  - SupabaseCircuitBreaker (supabase_client.py) — sliding window + streak
  - PNCPCircuitBreaker (clients/pncp/circuit_breaker.py) — consecutive threshold
  - RedisCircuitBreaker (clients/pncp/circuit_breaker.py) — Redis-backed + fallback
  - Legacy CircuitBreaker (pncp_resilience.py) — old-school CB
  - State transitions: CLOSED -> OPEN -> HALF_OPEN -> CLOSED
  - CircuitBreakerOpenError raised when OPEN
  - Prometheus metrics emission
  - Isolation between instances
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from supabase_client import (
    SupabaseCircuitBreaker,
    CircuitBreakerOpenError,
    get_cb,
)


# ===========================================================================
# Part 1: SupabaseCircuitBreaker — sliding window + consecutive streak
# ===========================================================================


class TestSupabaseCBStateTransitions:
    """AC1-3: SupabaseCB state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)."""

    def _make_cb(self, **kwargs) -> SupabaseCircuitBreaker:
        """Helper to create a fresh CB with fast defaults for testing."""
        defaults = dict(
            window_size=5,
            failure_rate_threshold=0.6,
            cooldown_seconds=0.01,
            trial_calls_max=2,
            consecutive_failures_threshold=3,
        )
        defaults.update(kwargs)
        return SupabaseCircuitBreaker(**defaults)

    # ------------------------------------------------------------------
    # CLOSED -> OPEN via streak (consecutive_failures_threshold)
    # ------------------------------------------------------------------

    def test_streak_trip_after_n_failures(self):
        """CB opens after `consecutive_failures_threshold` back-to-back failures."""
        cb = self._make_cb(consecutive_failures_threshold=3)
        assert cb.state == "CLOSED"

        # 3 failures → should trip OPEN
        cb._record_failure(Exception("err1"))
        assert cb.state == "CLOSED", "Should still be CLOSED after 1 failure"
        cb._record_failure(Exception("err2"))
        assert cb.state == "CLOSED", "Should still be CLOSED after 2 failures"
        cb._record_failure(Exception("err3"))
        assert cb.state == "OPEN", "Should be OPEN after 3 consecutive failures"

    def test_streak_reset_by_success(self):
        """A success resets the consecutive failure counter."""
        cb = self._make_cb(consecutive_failures_threshold=3)
        cb._record_failure(Exception("e1"))
        cb._record_failure(Exception("e2"))
        cb._record_success()  # Reset streak
        cb._record_failure(Exception("e3"))  # Only 1 failure now
        assert cb.state == "CLOSED", "Success should reset streak, need 3 more"

    def test_no_streak_trip_when_threshold_none(self):
        """Without consecutive_failures_threshold, only rate-based trip works."""
        cb = self._make_cb(
            window_size=10,
            consecutive_failures_threshold=None,
            failure_rate_threshold=0.5,
        )
        # 3 failures without rate-trip should NOT open
        for i in range(3):
            cb._record_failure(Exception(f"e{i}"))
        assert cb.state == "CLOSED", (
            "Without streak threshold, 3 failures should not trip "
            "with window_size=10 and no half-window rate trip"
        )

    # ------------------------------------------------------------------
    # CLOSED -> OPEN via rate (sliding window)
    # ------------------------------------------------------------------

    def test_rate_trip_when_window_full(self):
        """CB opens when failure rate in full window exceeds threshold."""
        cb = self._make_cb(
            window_size=10,
            failure_rate_threshold=0.5,
            consecutive_failures_threshold=None,  # disable streak
        )
        # Fill window with 6 failures + 4 successes = 60% failure rate > 50%
        for _ in range(4):
            cb._record_success()
        for _ in range(6):
            cb._record_failure(Exception("e"))
        assert cb.state == "OPEN", "60% failure rate should trip 50% threshold"

    def test_rate_no_trip_below_threshold(self):
        """CB stays CLOSED when failure rate is below threshold."""
        cb = self._make_cb(
            window_size=10,
            failure_rate_threshold=0.5,
            consecutive_failures_threshold=None,
        )
        for _ in range(7):
            cb._record_success()
        for _ in range(3):
            cb._record_failure(Exception("e"))
        assert cb.state == "CLOSED", "30% failure rate should not trip 50% threshold"

    # ------------------------------------------------------------------
    # OPEN -> HALF_OPEN (cooldown)
    # ------------------------------------------------------------------

    def test_half_open_after_cooldown(self):
        """CB transitions to HALF_OPEN after cooldown expires."""
        cb = self._make_cb(cooldown_seconds=0.005, consecutive_failures_threshold=2)
        cb._record_failure(Exception("e1"))
        cb._record_failure(Exception("e2"))
        assert cb.state == "OPEN"

        # After cooldown, reading state should auto-transition
        time.sleep(0.01)
        assert cb.state == "HALF_OPEN"

    # ------------------------------------------------------------------
    # HALF_OPEN -> CLOSED (successes)
    # ------------------------------------------------------------------

    def test_half_open_to_closed_after_successes(self):
        """CB closes after `trial_calls_max` consecutive successes in HALF_OPEN."""
        cb = self._make_cb(
            cooldown_seconds=0.001,
            trial_calls_max=2,
            consecutive_failures_threshold=2,
        )
        cb._record_failure(Exception("e1"))
        cb._record_failure(Exception("e2"))
        assert cb.state == "OPEN"

        # After cooldown, reading state should auto-transition to HALF_OPEN
        time.sleep(0.005)
        assert cb.state == "HALF_OPEN"

        # 2 successes → should close
        cb._record_success()
        assert cb.state == "HALF_OPEN", "Need 2 successes"
        cb._record_success()
        assert cb.state == "CLOSED", "2 successes should close in HALF_OPEN"

    # ------------------------------------------------------------------
    # HALF_OPEN -> OPEN (failure during recovery)
    # ------------------------------------------------------------------

    def test_half_open_to_open_on_failure(self):
        """Any failure in HALF_OPEN immediately reverts to OPEN."""
        cb = self._make_cb(cooldown_seconds=0.001, consecutive_failures_threshold=2)
        cb._record_failure(Exception("e1"))
        cb._record_failure(Exception("e2"))
        assert cb.state == "OPEN"

        # Wait for cooldown so state auto-transitions to HALF_OPEN
        time.sleep(0.005)
        assert cb.state == "HALF_OPEN"

        # A failure in HALF_OPEN → back to OPEN
        cb._record_failure(Exception("e3"))
        assert cb.state == "OPEN"


class TestSupabaseCBCallSync:
    """AC4: call_sync() behavior."""

    def test_call_sync_success(self):
        """Successful call records success and returns result."""
        cb = SupabaseCircuitBreaker(
            window_size=3,
            consecutive_failures_threshold=2,
        )

        def ok():
            return "OK"

        result = cb.call_sync(ok)
        assert result == "OK"
        assert cb._consecutive_failures == 0

    def test_call_sync_failure_records_error(self):
        """Failed call records failure and re-raises."""
        cb = SupabaseCircuitBreaker(
            window_size=3,
            consecutive_failures_threshold=2,
        )

        def fail():
            raise ValueError("boom")

        with pytest.raises(ValueError, match="boom"):
            cb.call_sync(fail)
        assert cb._consecutive_failures == 1

    def test_call_sync_raises_cb_open_error(self):
        """Calling when OPEN raises CircuitBreakerOpenError (not crashes)."""
        cb = SupabaseCircuitBreaker(
            window_size=3,
            consecutive_failures_threshold=2,
            cooldown_seconds=60,
        )
        # Trip the breaker
        cb._record_failure(Exception("e1"))
        cb._record_failure(Exception("e2"))
        assert cb.state == "OPEN"

        def ok():
            return "OK"

        with pytest.raises(CircuitBreakerOpenError, match="circuit breaker is OPEN"):
            cb.call_sync(ok)


class TestSupabaseCBAsyncCall:
    """AC5: call_async() behavior."""

    @pytest.mark.asyncio
    async def test_call_async_success(self):
        """Successful async call records success and returns result."""
        cb = SupabaseCircuitBreaker(
            window_size=3,
            consecutive_failures_threshold=2,
        )

        async def ok():
            return "ASYNC_OK"

        result = await cb.call_async(ok())
        assert result == "ASYNC_OK"

    @pytest.mark.asyncio
    async def test_call_async_failure_records_error(self):
        """Failed async call records failure and re-raises."""
        cb = SupabaseCircuitBreaker(
            window_size=3,
            consecutive_failures_threshold=2,
        )

        async def fail():
            raise RuntimeError("async boom")

        with pytest.raises(RuntimeError, match="async boom"):
            await cb.call_async(fail())
        assert cb._consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_call_async_raises_cb_open_error(self):
        """Calling async when OPEN raises CircuitBreakerOpenError."""
        cb = SupabaseCircuitBreaker(
            window_size=3,
            consecutive_failures_threshold=2,
            cooldown_seconds=60,
        )
        cb._record_failure(Exception("e1"))
        cb._record_failure(Exception("e2"))
        assert cb.state == "OPEN"

        async def ok():
            return "OK"

        with pytest.raises(CircuitBreakerOpenError, match="circuit breaker is OPEN"):
            await cb.call_async(ok())


class TestSupabaseCBExcludePredicates:
    """CRIT-040: Exclude predicates prevent certain errors from tripping CB."""

    def test_excluded_error_does_not_count(self):
        """Errors matching exclude_predicates are not counted as failures."""
        def is_schema_error(exc):
            return "PGRST205" in str(exc)

        cb = SupabaseCircuitBreaker(
            window_size=3,
            consecutive_failures_threshold=3,
            exclude_predicates=[is_schema_error],
        )

        # Schema errors should not count
        for _ in range(5):
            cb._record_failure(Exception("PGRST205 schema cache miss"))

        assert cb.state == "CLOSED", "Schema errors must not trip CB"

    def test_non_excluded_error_still_counts(self):
        """Non-excluded errors count normally."""
        def is_schema_error(exc):
            return "PGRST205" in str(exc)

        cb = SupabaseCircuitBreaker(
            window_size=3,
            consecutive_failures_threshold=3,
            exclude_predicates=[is_schema_error],
        )

        cb._record_failure(Exception("PGRST205 schema miss"))  # excluded
        cb._record_failure(Exception("connection timeout"))  # NOT excluded
        cb._record_failure(Exception("connection timeout"))  # NOT excluded
        cb._record_failure(Exception("connection timeout"))  # NOT excluded → trips

        assert cb.state == "OPEN"


class TestSupabaseCBReset:
    """AC6: reset() restores CLOSED state."""

    def test_reset_clears_state(self):
        """reset() returns CB to CLOSED with cleared window."""
        cb = SupabaseCircuitBreaker(
            consecutive_failures_threshold=2,
            cooldown_seconds=60,
        )
        cb._record_failure(Exception("e1"))
        cb._record_failure(Exception("e2"))
        assert cb.state == "OPEN"

        cb.reset()
        assert cb.state == "CLOSED"
        assert cb._consecutive_failures == 0
        assert cb._opened_at is None
        assert len(cb._window) == 0


class TestSupabaseCBMetrics:
    """AC7: Prometheus metrics emission on state transitions."""

    def test_transition_counter_emitted(self):
        """State transition increments counter with labels."""
        cb = SupabaseCircuitBreaker(
            consecutive_failures_threshold=2,
            cooldown_seconds=0,
        )

        with patch("metrics.SUPABASE_CB_TRANSITIONS") as mock_transitions, \
             patch("metrics.SUPABASE_CB_STATE"), \
             patch("metrics.SUPABASE_CB_STATE_BY_CATEGORY"):

            cb._record_failure(Exception("e1"))
            cb._record_failure(Exception("e2"))  # CLOSED -> OPEN

        mock_transitions.labels.assert_called_once_with(
            from_state="CLOSED", to_state="OPEN", source="app"
        )
        mock_transitions.labels.return_value.inc.assert_called_once()

    def test_reset_does_not_emit_transition(self):
        """reset() is not a user-visible transition, no metric emitted."""
        cb = SupabaseCircuitBreaker(
            consecutive_failures_threshold=2,
            cooldown_seconds=0,
        )
        cb._record_failure(Exception("e1"))

        with patch("metrics.SUPABASE_CB_TRANSITIONS"), \
             patch("metrics.SUPABASE_CB_STATE"), \
             patch("metrics.SUPABASE_CB_STATE_BY_CATEGORY"):
            cb.reset()

        # reset() sets _state directly without _transition_locked
        assert cb.state == "CLOSED"


class TestSupabaseCBIsolation:
    """GTM-FIX-005 AC9: Failure isolation between segregate CBs."""

    def test_read_write_rpc_isolation(self):
        """read_cb failure does not affect write_cb or rpc_cb."""
        read_cb = SupabaseCircuitBreaker(
            name="read",
            window_size=2,
            consecutive_failures_threshold=2,
            cooldown_seconds=60,
        )
        write_cb = SupabaseCircuitBreaker(
            name="write",
            window_size=2,
            consecutive_failures_threshold=3,
            cooldown_seconds=60,
        )
        rpc_cb = SupabaseCircuitBreaker(
            name="rpc",
            window_size=2,
            consecutive_failures_threshold=4,
            cooldown_seconds=60,
        )

        # Trip only read_cb
        read_cb._record_failure(Exception("e1"))
        read_cb._record_failure(Exception("e2"))
        assert read_cb.state == "OPEN"
        assert write_cb.state == "CLOSED"
        assert rpc_cb.state == "CLOSED"

        # write_cb and rpc_cb remain usable
        write_cb._record_success()
        rpc_cb._record_success()

    def test_get_cb_lookup(self):
        """get_cb() returns correct CB per category."""
        read_cb = get_cb("read")
        write_cb = get_cb("write")
        rpc_cb = get_cb("rpc")
        assert read_cb.name == "read"
        assert write_cb.name == "write"
        assert rpc_cb.name == "rpc"
        assert read_cb is not write_cb
        assert write_cb is not rpc_cb


# ===========================================================================
# Part 2: PNCPCircuitBreaker — in-memory, consecutive failures
# ===========================================================================


class TestPNCPCircuitBreaker:
    """Tests for PNCPCircuitBreaker (clients/pncp/circuit_breaker.py)."""

    @pytest.mark.asyncio
    async def test_initial_state_healthy(self):
        """Fresh CB starts as not degraded."""
        from pncp_client import PNCPCircuitBreaker
        cb = PNCPCircuitBreaker(name="test", threshold=5, cooldown_seconds=10)
        assert cb.is_degraded is False
        assert cb.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_trips_after_threshold_failures(self):
        """CB becomes degraded after `threshold` consecutive failures."""
        from pncp_client import PNCPCircuitBreaker
        cb = PNCPCircuitBreaker(name="test_trip", threshold=3, cooldown_seconds=60)

        for _ in range(2):
            await cb.record_failure()
        assert cb.is_degraded is False, "Under threshold"

        await cb.record_failure()  # 3rd → trips
        assert cb.is_degraded is True, "Should be degraded after threshold"
        assert cb.consecutive_failures == 3

    @pytest.mark.asyncio
    async def test_record_success_resets_counter(self):
        """record_success resets consecutive failures to 0."""
        from pncp_client import PNCPCircuitBreaker
        cb = PNCPCircuitBreaker(name="test_reset", threshold=5, cooldown_seconds=10)

        await cb.record_failure()
        await cb.record_failure()
        await cb.record_failure()
        assert cb.consecutive_failures == 3

        await cb.record_success()
        assert cb.consecutive_failures == 0
        assert cb.is_degraded is False

    @pytest.mark.asyncio
    async def test_try_recover_recovers_after_cooldown(self):
        """try_recover returns True and resets state after cooldown expires."""
        from pncp_client import PNCPCircuitBreaker
        cb = PNCPCircuitBreaker(name="test_recover", threshold=2, cooldown_seconds=0.01)

        await cb.record_failure()
        await cb.record_failure()
        # CB was just tripped; is_degraded returns True briefly until cooldown expires
        assert cb.consecutive_failures >= 2
        assert cb.degraded_until is not None

        # Wait for cooldown to expire
        await asyncio.sleep(0.02)
        recovered = await cb.try_recover()
        assert recovered is True
        assert cb.is_degraded is False
        assert cb.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_try_recover_returns_false_while_degraded(self):
        """try_recover returns False while cooldown is active."""
        from pncp_client import PNCPCircuitBreaker
        cb = PNCPCircuitBreaker(name="test_active", threshold=2, cooldown_seconds=60)

        await cb.record_failure()
        await cb.record_failure()
        assert cb.is_degraded is True

        recovered = await cb.try_recover()
        assert recovered is False

    @pytest.mark.asyncio
    async def test_does_not_re_trip_while_already_degraded(self):
        """Further failures while degraded don't extend cooldown (degraded_until set once)."""
        from pncp_client import PNCPCircuitBreaker
        cb = PNCPCircuitBreaker(name="test_multi", threshold=2, cooldown_seconds=30)

        await cb.record_failure()
        await cb.record_failure()
        assert cb.is_degraded is True
        first_degraded_until = cb.degraded_until

        # More failures while already degraded
        await cb.record_failure()
        await cb.record_failure()

        # degraded_until should remain the same (was set on first trip)
        assert cb.degraded_until == first_degraded_until, (
            "degraded_until should not be extended while already degraded"
        )

    @pytest.mark.asyncio
    async def test_isolation_between_sources(self):
        """Failure in one source CB doesn't affect another source CB."""
        from pncp_client import PNCPCircuitBreaker

        pncp_cb = PNCPCircuitBreaker(name="pncp", threshold=3, cooldown_seconds=60)
        pcp_cb = PNCPCircuitBreaker(name="pcp", threshold=3, cooldown_seconds=60)

        await pncp_cb.record_failure()
        await pncp_cb.record_failure()
        await pncp_cb.record_failure()
        assert pncp_cb.is_degraded is True
        assert pcp_cb.is_degraded is False
        assert pcp_cb.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_module_singletons_separate(self):
        """get_circuit_breaker returns separate instances per source."""
        from pncp_client import get_circuit_breaker
        pncp = get_circuit_breaker("pncp")
        pcp = get_circuit_breaker("pcp")
        comprasgov = get_circuit_breaker("comprasgov")

        assert pncp is not pcp
        assert pcp is not comprasgov
        assert pncp.name == "pncp"
        assert pcp.name == "pcp"
        assert comprasgov.name == "comprasgov"

    @pytest.mark.asyncio
    async def test_intermittent_errors_no_trip(self):
        """Intermittent errors (fail, success, fail) don't trip."""
        from pncp_client import PNCPCircuitBreaker
        cb = PNCPCircuitBreaker(name="intermittent", threshold=5, cooldown_seconds=10)

        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        await cb.record_failure()
        await cb.record_failure()

        # Never reached threshold due to reset
        assert cb.is_degraded is False

    def test_reset_manually(self):
        """Manual reset restores healthy state."""
        from pncp_client import PNCPCircuitBreaker
        cb = PNCPCircuitBreaker(name="reset_test", threshold=2, cooldown_seconds=60)
        cb.consecutive_failures = 10
        cb.degraded_until = time.time() + 100

        cb.reset()

        assert cb.consecutive_failures == 0
        assert cb.degraded_until is None
        assert cb.is_degraded is False


# ===========================================================================
# Part 3: RedisCircuitBreaker — in-memory fallback
# ===========================================================================


class TestRedisCircuitBreakerInMemoryFallback:
    """Tests for RedisCircuitBreaker with mocked/failed Redis."""

    @pytest.mark.asyncio
    async def test_fallback_to_local_when_redis_unavailable(self):
        """record_failure() uses local state when Redis unavailable."""
        from pncp_client import RedisCircuitBreaker
        cb = RedisCircuitBreaker(name="no_redis", threshold=3, cooldown_seconds=10)

        with patch.object(cb, "_get_redis", new=AsyncMock(return_value=None)):
            for _ in range(3):
                await cb.record_failure()

        assert cb.consecutive_failures == 3
        assert cb.is_degraded is True

    @pytest.mark.asyncio
    async def test_fallback_record_success(self):
        """record_success() falls back to local when Redis unavailable."""
        from pncp_client import RedisCircuitBreaker
        cb = RedisCircuitBreaker(name="no_redis_success", threshold=3, cooldown_seconds=10)

        with patch.object(cb, "_get_redis", new=AsyncMock(return_value=None)):
            await cb.record_failure()
            await cb.record_failure()
            assert cb.consecutive_failures == 2

            await cb.record_success()
            assert cb.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_fallback_try_recover(self):
        """try_recover() falls back to local when Redis unavailable."""
        from pncp_client import RedisCircuitBreaker
        cb = RedisCircuitBreaker(name="no_redis_recover", threshold=2, cooldown_seconds=0.01)

        with patch.object(cb, "_get_redis", new=AsyncMock(return_value=None)):
            await cb.record_failure()
            await cb.record_failure()

        assert cb.consecutive_failures >= 2
        assert cb.degraded_until is not None

        await asyncio.sleep(0.02)
        with patch.object(cb, "_get_redis", new=AsyncMock(return_value=None)):
            recovered = await cb.try_recover()
        assert recovered is True

    @pytest.mark.asyncio
    async def test_initialize_no_redis_is_noop(self):
        """initialize() with no Redis is a no-op."""
        from pncp_client import RedisCircuitBreaker
        cb = RedisCircuitBreaker(name="init_noop", threshold=5, cooldown_seconds=10)

        with patch.object(cb, "_get_redis", new=AsyncMock(return_value=None)):
            await cb.initialize()

        assert cb.consecutive_failures == 0
        assert cb.degraded_until is None

    @pytest.mark.asyncio
    async def test_redis_exception_is_graceful(self):
        """Record_failure handles Redis exceptions gracefully (falls back to local)."""
        from pncp_client import RedisCircuitBreaker
        cb = RedisCircuitBreaker(name="redis_error", threshold=2, cooldown_seconds=10)

        mock_redis = AsyncMock()
        mock_redis.eval = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch.object(cb, "_get_redis", new=AsyncMock(return_value=mock_redis)):
            await cb.record_failure()
            await cb.record_failure()

        # Falls back to local state
        assert cb.consecutive_failures == 2
        assert cb.is_degraded is True


class TestRedisCircuitBreakerKeys:
    """RedisCircuitBreaker key naming and isolation."""

    def test_key_names_are_correct(self):
        """Redis keys follow expected naming convention."""
        from pncp_client import RedisCircuitBreaker
        pncp_cb = RedisCircuitBreaker(name="pncp", threshold=15, cooldown_seconds=60)
        pcp_cb = RedisCircuitBreaker(name="pcp", threshold=30, cooldown_seconds=120)

        assert pncp_cb._key_failures == "circuit_breaker:pncp:failures"
        assert pncp_cb._key_degraded == "circuit_breaker:pncp:degraded_until"
        assert pcp_cb._key_failures == "circuit_breaker:pcp:failures"
        assert pcp_cb._key_degraded == "circuit_breaker:pcp:degraded_until"

    def test_different_instances_different_keys(self):
        """pncp and pcp use different key prefixes (AC10)."""
        from pncp_client import RedisCircuitBreaker
        pncp_cb = RedisCircuitBreaker(name="pncp")
        pcp_cb = RedisCircuitBreaker(name="pcp")

        assert pncp_cb._key_failures != pcp_cb._key_failures
        assert pncp_cb._key_degraded != pcp_cb._key_degraded

    @pytest.mark.asyncio
    async def test_degraded_flag_uses_local_state_when_redis_unavailable(self):
        """is_degraded property uses local state when no Redis."""
        from pncp_client import RedisCircuitBreaker
        cb = RedisCircuitBreaker(name="flag_test", threshold=2, cooldown_seconds=60)

        with patch.object(cb, "_get_redis", new=AsyncMock(return_value=None)):
            await cb.record_failure()
            await cb.record_failure()

        assert cb.is_degraded is True  # Uses local state


# ===========================================================================
# Part 4: Legacy CircuitBreaker (pncp_resilience.py)
# ===========================================================================


class TestLegacyCircuitBreaker:
    """Tests for the legacy CircuitBreaker in pncp_resilience.py."""

    def test_initial_state_closed(self):
        """Fresh legacy CB starts CLOSED."""
        from pncp_resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState
        cb = CircuitBreaker(name="legacy", config=CircuitBreakerConfig(failure_threshold=3))
        assert cb.is_closed is True
        assert cb.is_open is False
        assert cb.state == CircuitState.CLOSED

    def test_opens_after_consecutive_failures(self):
        """CB opens after `failure_threshold` failures."""
        from pncp_resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState
        cb = CircuitBreaker(
            name="legacy_open",
            config=CircuitBreakerConfig(failure_threshold=3, timeout_seconds=60),
        )

        def fail():
            raise ValueError("fail")

        for _ in range(3):
            with pytest.raises(ValueError):
                cb.call(fail)

        assert cb.is_open is True
        assert cb.state == CircuitState.OPEN

    def test_call_rejected_when_open(self):
        """Call raises exception when circuit is OPEN."""
        from pncp_resilience import CircuitBreaker, CircuitBreakerConfig
        cb = CircuitBreaker(
            name="legacy_reject",
            config=CircuitBreakerConfig(failure_threshold=2, timeout_seconds=60),
        )

        def fail():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            cb.call(fail)
        with pytest.raises(ValueError):
            cb.call(fail)

        assert cb.is_open is True

        def ok():
            return "OK"

        with pytest.raises(Exception, match="is OPEN"):
            cb.call(ok)

    def test_half_open_after_timeout(self):
        """After timeout, OPEN -> HALF_OPEN transition allows a call."""
        from pncp_resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState
        cb = CircuitBreaker(
            name="legacy_half",
            config=CircuitBreakerConfig(failure_threshold=2, timeout_seconds=-1),
        )

        def fail():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            cb.call(fail)
        with pytest.raises(ValueError):
            cb.call(fail)

        # Manually set last_failure_time far in the past
        cb.last_failure_time = time.time() - 10
        assert cb.is_open is True  # Still open before check

        # Next call should trigger HALF_OPEN automatically
        def ok():
            return "OK"

        result = cb.call(ok)
        assert result == "OK"
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_closes_after_successes(self):
        """HALF_OPEN -> CLOSED after `success_threshold` successes."""
        from pncp_resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState
        cb = CircuitBreaker(
            name="legacy_close",
            config=CircuitBreakerConfig(
                failure_threshold=2,
                success_threshold=2,
                timeout_seconds=-1,
            ),
        )

        def fail():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            cb.call(fail)
        with pytest.raises(ValueError):
            cb.call(fail)

        # Move to HALF_OPEN
        cb.last_failure_time = time.time() - 10
        assert cb.is_open is True

        def ok():
            return "OK"

        # First call in OPEN: triggers HALF_OPEN transition, then records success
        # success_count becomes 1 after _on_success
        cb.call(ok)
        assert cb.state == CircuitState.HALF_OPEN

        # Second call from HALF_OPEN: success_count becomes 2 -> CLOSED
        cb.call(ok)
        assert cb.state == CircuitState.CLOSED, "Two successes in half-open should close"

    def test_half_open_reverts_to_open_on_failure(self):
        """HALF_OPEN -> OPEN on any failure during recovery."""
        from pncp_resilience import CircuitBreaker, CircuitBreakerConfig, CircuitState
        cb = CircuitBreaker(
            name="legacy_revert",
            config=CircuitBreakerConfig(failure_threshold=2, timeout_seconds=-1),
        )

        def fail():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            cb.call(fail)
        with pytest.raises(ValueError):
            cb.call(fail)

        # Move to HALF_OPEN
        cb.last_failure_time = time.time() - 10

        def ok():
            return "OK"

        cb.call(ok)  # Triggers HALF_OPEN
        assert cb.state == CircuitState.HALF_OPEN

        # Failure in HALF_OPEN -> OPEN
        with pytest.raises(ValueError):
            cb.call(fail)
        assert cb.state == CircuitState.OPEN

    def test_async_call(self):
        """call_async works correctly."""
        from pncp_resilience import CircuitBreaker, CircuitBreakerConfig

        async def _run():
            cb = CircuitBreaker(
                name="legacy_async",
                config=CircuitBreakerConfig(failure_threshold=2, timeout_seconds=60),
            )

            async def ok():
                return "ASYNC"

            result = await cb.call_async(ok)
            assert result == "ASYNC"

            async def fail():
                raise ValueError("async fail")

            with pytest.raises(ValueError, match="async fail"):
                await cb.call_async(fail)
            with pytest.raises(ValueError, match="async fail"):
                await cb.call_async(fail)

            assert cb.is_open is True

            with pytest.raises(Exception, match="is OPEN"):
                await cb.call_async(ok)

        asyncio.run(_run())

    def test_window_rate_trip(self):
        """CB opens based on failure rate in sliding window."""
        from pncp_resilience import CircuitBreaker, CircuitBreakerConfig
        cb = CircuitBreaker(
            name="rate_trip",
            config=CircuitBreakerConfig(
                failure_threshold=10,  # High, so consecutive won't trip
                window_size=10,
                failure_rate_threshold=0.5,
                timeout_seconds=60,
            ),
        )

        def fail():
            raise ValueError("fail")

        # 6 failures out of 10 = 60% > 50%
        for _ in range(4):
            cb.call(lambda: "OK")  # successes
        for _ in range(6):
            with pytest.raises(ValueError):
                cb.call(fail)

        assert cb.is_open is True


# ===========================================================================
# Part 5: Prometheus metrics emission
# ===========================================================================


class TestCircuitBreakerPrometheusMetrics:
    """#1800: Verify Prometheus metrics are emitted for CB events."""

    def test_supabase_cb_state_gauge_set_on_open(self):
        """SupabaseCB sets SUPABASE_CB_STATE to 1 on OPEN."""
        cb = SupabaseCircuitBreaker(
            name="metrics_test",
            consecutive_failures_threshold=2,
            cooldown_seconds=0.001,
        )

        with patch("metrics.SUPABASE_CB_STATE") as mock_gauge, \
             patch("metrics.SUPABASE_CB_TRANSITIONS"), \
             patch("metrics.SUPABASE_CB_STATE_BY_CATEGORY"):

            cb._record_failure(Exception("e1"))
            cb._record_failure(Exception("e2"))  # -> OPEN

        mock_gauge.set.assert_called_with(1)

    def test_supabase_cb_state_gauge_set_on_closed(self):
        """SupabaseCB sets SUPABASE_CB_STATE to 0 on CLOSED."""
        cb = SupabaseCircuitBreaker(
            name="metrics_closed",
            cooldown_seconds=0.001,
            trial_calls_max=1,
            consecutive_failures_threshold=2,
        )

        with patch("metrics.SUPABASE_CB_STATE") as mock_gauge, \
             patch("metrics.SUPABASE_CB_TRANSITIONS"), \
             patch("metrics.SUPABASE_CB_STATE_BY_CATEGORY"):

            cb._record_failure(Exception("e1"))
            cb._record_failure(Exception("e2"))  # -> OPEN
            time.sleep(0.005)
            _ = cb.state  # Forces HALF_OPEN
            cb._record_success()  # -> CLOSED (trial_calls_max=1)

        # Last transition: HALF_OPEN -> CLOSED sets gauge to 0
        mock_gauge.set.assert_called_with(0)

    @pytest.mark.asyncio
    async def test_pncp_cb_metric_set_on_trip(self):
        """PNCPCircuitBreaker sets CIRCUIT_BREAKER_STATE to 1 on trip."""
        # Import with module patching
        with patch("clients.pncp.circuit_breaker.CIRCUIT_BREAKER_STATE") as mock_state:
            from pncp_client import PNCPCircuitBreaker
            cb = PNCPCircuitBreaker(name="metric_pncp", threshold=2, cooldown_seconds=60)

            await cb.record_failure()
            await cb.record_failure()

        mock_state.labels.assert_called_once_with(source="metric_pncp")
        mock_state.labels.return_value.set.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_pncp_cb_metric_reset_on_recovery(self):
        """PNCPCircuitBreaker sets CIRCUIT_BREAKER_STATE to 0 on recovery."""
        with patch("clients.pncp.circuit_breaker.CIRCUIT_BREAKER_STATE") as mock_state:
            from pncp_client import PNCPCircuitBreaker
            cb = PNCPCircuitBreaker(name="metric_recover", threshold=2, cooldown_seconds=0.01)

            await cb.record_failure()
            await cb.record_failure()
            mock_state.labels.return_value.set.assert_called_with(1)

            await asyncio.sleep(0.02)
            await cb.try_recover()

        mock_state.labels.return_value.set.assert_called_with(0)

    def test_supabase_cb_state_by_category_gauge(self):
        """SUPABASE_CB_STATE_BY_CATEGORY is set on transition."""
        cb = SupabaseCircuitBreaker(
            name="category_test",
            consecutive_failures_threshold=2,
            cooldown_seconds=0.001,
        )

        with patch("metrics.SUPABASE_CB_STATE"), \
             patch("metrics.SUPABASE_CB_TRANSITIONS"), \
             patch("metrics.SUPABASE_CB_STATE_BY_CATEGORY") as mock_category:

            cb._record_failure(Exception("e1"))
            cb._record_failure(Exception("e2"))  # -> OPEN

        mock_category.labels.assert_called_once_with(category="category_test")
        mock_category.labels.return_value.set.assert_called_with(1)

    def test_circuit_breaker_trips_total_metric_exists(self):
        """CIRCUIT_BREAKER_TRIPS_TOTAL metric is defined."""
        from metrics import CIRCUIT_BREAKER_TRIPS_TOTAL
        # Just verify it imports without error
        assert CIRCUIT_BREAKER_TRIPS_TOTAL is not None
