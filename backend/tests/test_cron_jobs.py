"""Tests for cron_jobs.py — periodic cache cleanup, session cleanup, canary tasks,
schedule validation, distributed lock mechanics, and resilience of all 19+ lifespan
loop cron jobs (F-03 #1774).

Wave 0 Safety Net: Covers get_pncp_cron_status, _update_pncp_cron_status,
_is_cb_or_connection_error, cleanup_stale_sessions, and config constants.

Wave 1 Coverage (F-03): Import verification, schedule parameter validation,
docstring audits, distributed lock simulation, and mocked execution of key
cron jobs across all jobs.cron.* modules.

Note: Tests for refresh_stale_cache_entries, warmup_top_params, and
_get_prioritized_ufs were removed on 2026-04-18 along with the underlying
code (STORY-CIG-BE-cache-warming-deprecate — cache warming proativo
substituido pelo DataLake Supabase).
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from types import SimpleNamespace
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cron_jobs import (
    get_pncp_cron_status,
    get_pncp_recovery_epoch,
    _update_pncp_cron_status,
    _is_cb_or_connection_error,
    cleanup_stale_sessions,
    CLEANUP_INTERVAL_SECONDS,
    SESSION_STALE_HOURS,
    SESSION_OLD_DAYS,
)


@pytest.fixture(autouse=True)
def _reset_pncp_status():
    """Reset PNCP cron status between tests."""
    import cron_jobs
    with cron_jobs._pncp_cron_status_lock:
        cron_jobs._pncp_cron_status.update(
            {"status": "unknown", "latency_ms": None, "updated_at": None}
        )
        cron_jobs._pncp_recovery_epoch = 0
    yield


# ──────────────────────────────────────────────────────────────────────
# get_pncp_cron_status / _update_pncp_cron_status
# ──────────────────────────────────────────────────────────────────────

class TestPncpCronStatus:
    """Tests for PNCP cron canary status."""

    @pytest.mark.timeout(30)
    def test_initial_status(self):
        status = get_pncp_cron_status()
        assert status["status"] == "unknown"
        assert status["latency_ms"] is None

    @pytest.mark.timeout(30)
    def test_update_healthy(self):
        _update_pncp_cron_status("healthy", 150)
        status = get_pncp_cron_status()
        assert status["status"] == "healthy"
        assert status["latency_ms"] == 150
        assert status["updated_at"] is not None

    @pytest.mark.timeout(30)
    def test_update_degraded(self):
        _update_pncp_cron_status("degraded", 5000)
        status = get_pncp_cron_status()
        assert status["status"] == "degraded"

    @pytest.mark.timeout(30)
    def test_recovery_epoch_increments(self):
        """CRIT-056 AC4: Recovery from degraded->healthy increments epoch."""
        _update_pncp_cron_status("degraded", 5000)
        assert get_pncp_recovery_epoch() == 0
        _update_pncp_cron_status("healthy", 100)
        assert get_pncp_recovery_epoch() == 1

    @pytest.mark.timeout(30)
    def test_no_epoch_increment_on_healthy_to_healthy(self):
        _update_pncp_cron_status("healthy", 100)
        _update_pncp_cron_status("healthy", 120)
        assert get_pncp_recovery_epoch() == 0

    @pytest.mark.timeout(30)
    def test_down_to_healthy_increments(self):
        _update_pncp_cron_status("down", None)
        _update_pncp_cron_status("healthy", 200)
        assert get_pncp_recovery_epoch() == 1

    @pytest.mark.timeout(30)
    def test_returns_dict_copy(self):
        _update_pncp_cron_status("healthy", 100)
        status1 = get_pncp_cron_status()
        status1["status"] = "modified"
        status2 = get_pncp_cron_status()
        assert status2["status"] == "healthy"


# ──────────────────────────────────────────────────────────────────────
# _is_cb_or_connection_error
# ──────────────────────────────────────────────────────────────────────

class TestIsCbOrConnectionError:
    """Tests for circuit breaker / connection error detection."""

    @pytest.mark.timeout(30)
    def test_circuit_breaker_error(self):
        assert _is_cb_or_connection_error(
            type("CircuitBreakerOpenError", (Exception,), {})("CB is open")
        ) is True

    @pytest.mark.timeout(30)
    def test_connection_error(self):
        assert _is_cb_or_connection_error(ConnectionError("refused")) is True

    @pytest.mark.timeout(30)
    def test_connect_error_in_message(self):
        assert _is_cb_or_connection_error(Exception("ConnectError: timeout")) is True

    @pytest.mark.timeout(30)
    def test_pgrst205_in_message(self):
        assert _is_cb_or_connection_error(Exception("PGRST205: table not found")) is True

    @pytest.mark.timeout(30)
    def test_generic_error(self):
        assert _is_cb_or_connection_error(ValueError("bad input")) is False

    @pytest.mark.timeout(30)
    def test_empty_error(self):
        assert _is_cb_or_connection_error(Exception("")) is False


# ──────────────────────────────────────────────────────────────────────
# cleanup_stale_sessions
# ──────────────────────────────────────────────────────────────────────

class TestCleanupStaleSessions:
    """Tests for session cleanup task."""

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_happy_path(self, mock_execute, mock_get_sb):
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        mock_sb.table.return_value = mock_sb
        mock_sb.update.return_value = mock_sb
        mock_sb.delete.return_value = mock_sb
        mock_sb.eq.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb

        mock_execute.return_value = SimpleNamespace(data=[])

        result = await cleanup_stale_sessions()
        assert "marked_stale" in result
        assert "deleted_old" in result
        assert result["marked_stale"] == 0
        assert result["deleted_old"] == 0

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase", side_effect=Exception("DB down"))
    async def test_error_handling(self, mock_get_sb):
        result = await cleanup_stale_sessions()
        assert "error" in result

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_schema_fallback(self, mock_execute, mock_get_sb):
        """When status column missing, falls back to created_at cleanup."""
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.update.return_value = mock_sb
        mock_sb.delete.return_value = mock_sb
        mock_sb.eq.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb

        call_count = [0]

        async def side_effect(query):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("42703: undefined column 'status'")
            return SimpleNamespace(data=[])

        mock_execute.side_effect = side_effect

        result = await cleanup_stale_sessions()
        assert "deleted_old" in result


# ──────────────────────────────────────────────────────────────────────
# Constants sanity checks
# ──────────────────────────────────────────────────────────────────────

class TestConstants:
    """Sanity checks for cron job configuration."""

    @pytest.mark.timeout(30)
    def test_cleanup_interval(self):
        assert CLEANUP_INTERVAL_SECONDS == 6 * 60 * 60

    @pytest.mark.timeout(30)
    def test_session_thresholds(self):
        assert SESSION_STALE_HOURS == 1
        assert SESSION_OLD_DAYS == 7


# ──────────────────────────────────────────────────────────────────────
# _update_pncp_cron_status — extended
# ──────────────────────────────────────────────────────────────────────

class TestPncpRecoveryEpoch:
    """Tests for recovery epoch tracking (CRIT-056)."""

    @pytest.mark.timeout(30)
    def test_epoch_not_incremented_on_healthy_to_healthy(self):
        _update_pncp_cron_status("healthy", 50)
        epoch_before = get_pncp_recovery_epoch()
        _update_pncp_cron_status("healthy", 40)
        assert get_pncp_recovery_epoch() == epoch_before

    @pytest.mark.timeout(30)
    def test_epoch_not_incremented_on_healthy_to_degraded(self):
        _update_pncp_cron_status("healthy", 50)
        epoch_before = get_pncp_recovery_epoch()
        _update_pncp_cron_status("degraded", None)
        assert get_pncp_recovery_epoch() == epoch_before

    @pytest.mark.timeout(30)
    def test_epoch_incremented_on_down_to_healthy(self):
        _update_pncp_cron_status("down", None)
        epoch_before = get_pncp_recovery_epoch()
        _update_pncp_cron_status("healthy", 30)
        assert get_pncp_recovery_epoch() == epoch_before + 1

    @pytest.mark.timeout(30)
    def test_epoch_incremented_on_degraded_to_healthy(self):
        _update_pncp_cron_status("degraded", 500)
        epoch_before = get_pncp_recovery_epoch()
        _update_pncp_cron_status("healthy", 100)
        assert get_pncp_recovery_epoch() == epoch_before + 1

    @pytest.mark.timeout(30)
    def test_multiple_recovery_cycles(self):
        """Multiple degraded -> healthy cycles increment epoch each time."""
        for i in range(3):
            _update_pncp_cron_status("degraded", None)
            _update_pncp_cron_status("healthy", 50)
        assert get_pncp_recovery_epoch() == 3


# ──────────────────────────────────────────────────────────────────────
# _is_cb_or_connection_error — extended
# ──────────────────────────────────────────────────────────────────────

class TestIsCbOrConnectionErrorExtended:
    """Extended error classification tests."""

    @pytest.mark.timeout(30)
    def test_regular_value_error(self):
        assert not _is_cb_or_connection_error(ValueError("bad value"))

    @pytest.mark.timeout(30)
    def test_pgrst205_in_message(self):
        assert _is_cb_or_connection_error(Exception("PGRST205: schema cache"))

    @pytest.mark.timeout(30)
    def test_runtime_error(self):
        assert not _is_cb_or_connection_error(RuntimeError("something"))

    @pytest.mark.timeout(30)
    def test_connect_error_in_message(self):
        assert _is_cb_or_connection_error(Exception("ConnectError: timed out"))


# ──────────────────────────────────────────────────────────────────────
# cleanup_stale_sessions — extended
# ──────────────────────────────────────────────────────────────────────

class TestCleanupStaleSessionsExtended:
    """Extended session cleanup tests."""

    @pytest.mark.timeout(30)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_column_error_fallback(self, mock_exec, mock_get_sb):
        """42703 error triggers created_at-only cleanup."""
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb

        call_count = [0]
        async def _exec_side(query):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("42703: column status does not exist")
            result = MagicMock()
            result.data = [{"id": "x"}]
            return result

        mock_exec.side_effect = _exec_side
        result = await cleanup_stale_sessions()
        assert result["marked_stale"] == 0
        assert result["deleted_old"] >= 0


# ======================================================================
# F-03 WAVE 1: Schedule validation, import checks, docstring audit,
# distributed lock mechanics, and mocked resilience tests.
# ======================================================================


# ──────────────────────────────────────────────────────────────────────
# Schedule parameter validation
# ──────────────────────────────────────────────────────────────────────

class TestScheduleConstants:
    """Validate that all cron schedule constants are positive and sane.

    Every *INTERVAL_SECONDS constant in the cron modules must be > 0
    and within expected bounds. This prevents accidental misconfiguration
    from cascading into runaway loops or never-running jobs.
    """

    @pytest.mark.timeout(30)
    def test_health_canary_interval(self):
        from jobs.cron.canary import HEALTH_CANARY_INTERVAL_SECONDS
        assert HEALTH_CANARY_INTERVAL_SECONDS > 0
        assert HEALTH_CANARY_INTERVAL_SECONDS <= 600  # at most 10 min

    @pytest.mark.timeout(30)
    def test_session_cleanup_intervals(self):
        from jobs.cron.session_cleanup import (
            CLEANUP_INTERVAL_SECONDS as sci,
            RESULTS_CLEANUP_INTERVAL_SECONDS as rci,
            SESSION_STALE_HOURS as ssh,
            SESSION_OLD_DAYS as sod,
        )
        assert sci == 6 * 60 * 60
        assert rci == 6 * 60 * 60
        assert ssh == 1
        assert sod == 7

    @pytest.mark.timeout(30)
    def test_notification_intervals(self):
        from jobs.cron.notifications import (
            TRIAL_SEQUENCE_INTERVAL_SECONDS,
            ALERTS_LOCK_TTL,
        )
        assert TRIAL_SEQUENCE_INTERVAL_SECONDS == 2 * 60 * 60
        assert ALERTS_LOCK_TTL == 30 * 60

    @pytest.mark.timeout(30)
    def test_notification_hours(self):
        from jobs.cron.notifications import SECTOR_STATS_HOUR_UTC, DAILY_VOLUME_HOUR_UTC
        assert 0 <= SECTOR_STATS_HOUR_UTC <= 23
        assert 0 <= DAILY_VOLUME_HOUR_UTC <= 23

    @pytest.mark.timeout(30)
    def test_billing_intervals(self):
        from jobs.cron.billing import (
            RECONCILIATION_LOCK_TTL,
            PRE_DUNNING_INTERVAL_SECONDS,
            PLAN_RECONCILIATION_INTERVAL,
            STRIPE_PURGE_INTERVAL_SECONDS,
        )
        assert RECONCILIATION_LOCK_TTL == 30 * 60
        assert PRE_DUNNING_INTERVAL_SECONDS == 24 * 60 * 60
        assert PLAN_RECONCILIATION_INTERVAL == 12 * 60 * 60
        assert STRIPE_PURGE_INTERVAL_SECONDS == 24 * 60 * 60

    @pytest.mark.timeout(30)
    def test_billing_lock_keys(self):
        from jobs.cron.billing import (
            RECONCILIATION_LOCK_KEY,
            REVENUE_SHARE_LOCK_KEY,
            PLAN_RECONCILIATION_LOCK_KEY,
        )
        assert "smartlic" in RECONCILIATION_LOCK_KEY
        assert "lock" in RECONCILIATION_LOCK_KEY
        assert "smartlic" in REVENUE_SHARE_LOCK_KEY
        assert "smartlic" in PLAN_RECONCILIATION_LOCK_KEY

    @pytest.mark.timeout(30)
    def test_cron_monitor_interval(self):
        from jobs.cron.cron_monitor import CRON_MONITOR_INTERVAL_SECONDS
        assert CRON_MONITOR_INTERVAL_SECONDS == 3600

    @pytest.mark.timeout(30)
    def test_auth_cleanup_interval(self):
        from jobs.cron.auth_cleanup import AUTH_CLEANUP_INTERVAL_SECONDS
        assert AUTH_CLEANUP_INTERVAL_SECONDS == 24 * 60 * 60

    @pytest.mark.timeout(30)
    def test_auth_cleanup_idle_hours(self):
        from jobs.cron.auth_cleanup import ATTEMPT_IDLE_HOURS
        assert ATTEMPT_IDLE_HOURS == 24

    @pytest.mark.timeout(30)
    def test_lead_magnet_intervals(self):
        from jobs.cron.send_lead_magnet import (
            LEAD_MAGNET_BATCH_INTERVAL_S,
            LEAD_MAGNET_BATCH_MAX,
        )
        assert LEAD_MAGNET_BATCH_INTERVAL_S == 300
        assert LEAD_MAGNET_BATCH_MAX == 50

    @pytest.mark.timeout(30)
    def test_metrics_refresh_interval(self):
        from jobs.cron.metrics_refresh import METRICS_REFRESH_INTERVAL_SECONDS, TARGET_UTC_HOUR
        assert METRICS_REFRESH_INTERVAL_SECONDS == 24 * 60 * 60
        assert TARGET_UTC_HOUR == 5

    @pytest.mark.timeout(30)
    def test_seo_coverage_manifest_job_name(self):
        from jobs.cron.seo_coverage_manifest import _JOB_NAME
        assert _JOB_NAME == "seo_coverage_manifest_job"

    @pytest.mark.timeout(30)
    def test_new_bids_notifier_hour(self):
        from jobs.cron.new_bids_notifier import NEW_BIDS_NOTIFIER_HOUR_UTC
        assert NEW_BIDS_NOTIFIER_HOUR_UTC == 12

    @pytest.mark.timeout(30)
    def test_indice_municipal_interval(self):
        from jobs.cron.indice_municipal import INDICE_MUNICIPAL_INTERVAL
        assert INDICE_MUNICIPAL_INTERVAL == 90 * 24 * 60 * 60

    @pytest.mark.timeout(30)
    def test_billing_reconciliation_interval(self):
        from jobs.cron.billing_reconciliation import RECON_INTERVAL_SECONDS, RECON_TARGET_HOUR_UTC
        assert RECON_INTERVAL_SECONDS == 24 * 60 * 60
        assert RECON_TARGET_HOUR_UTC == 3

    @pytest.mark.timeout(30)
    def test_trial_risk_hour(self):
        from jobs.cron.trial_risk_detection import TRIAL_RISK_HOUR_UTC
        assert TRIAL_RISK_HOUR_UTC == 12

    @pytest.mark.timeout(30)
    def test_competitive_alert_job_constants(self):
        from jobs.cron.competitive_alert_job import _WEEKLY_DIGEST_WEEKDAY, _WEEKLY_DIGEST_HOUR_UTC
        assert _WEEKLY_DIGEST_WEEKDAY == 0  # Monday
        assert _WEEKLY_DIGEST_HOUR_UTC == 11

    @pytest.mark.timeout(30)
    def test_cache_cleanup_interval(self):
        from cron.cache import CLEANUP_INTERVAL_SECONDS
        assert CLEANUP_INTERVAL_SECONDS == 6 * 60 * 60


# ──────────────────────────────────────────────────────────────────────
# Import verification — every cron module loads without error
# ──────────────────────────────────────────────────────────────────────

class TestCronModuleImports:
    """Verify every cron module can be imported without ImportError.

    Covers all modules in jobs/cron/*.py, cron/*.py, and cron_jobs.py.
    """

    MODULES = [
        "cron_jobs",
        "jobs.cron.canary",
        "jobs.cron.session_cleanup",
        "jobs.cron.notifications",
        "jobs.cron.billing",
        "jobs.cron.trial_risk_detection",
        "jobs.cron.cron_monitor",
        "jobs.cron.send_lead_magnet",
        "jobs.cron.auth_cleanup",
        "jobs.cron.indice_municipal",
        "jobs.cron.new_bids_notifier",
        "jobs.cron.seo_snapshot",
        "jobs.cron.seo_coverage_manifest",
        "jobs.cron.pncp_canary",
        "jobs.cron.llm_batch_poll",
        "jobs.cron.metrics_refresh",
        "jobs.cron.scheduler",
        "jobs.cron.billing_reconciliation",
        "jobs.cron.founders_auto_disable",
        "jobs.cron.competitive_alert_job",
        "jobs.cron.network_events_cleanup",
        "jobs.cron.subcontract_discovery",
        "jobs.cron.gsc_sync",
        "jobs.cron.monthly_report_job",
        "jobs.cron.predictive_alert_job",
        "cron.cache",
        "cron._loop",
    ]

    @pytest.mark.timeout(10)
    @pytest.mark.parametrize("modname", MODULES)
    def test_module_import(self, modname):
        __import__(modname)
        # If we get here, the import succeeded
        assert modname in sys.modules


# ──────────────────────────────────────────────────────────────────────
# Docstring audit — every cron function should have one
# ──────────────────────────────────────────────────────────────────────

class TestCronDocstrings:
    """Key cron functions must have meaningful docstrings.

    This is a lightweight audit: while not every helper needs a
    docstring, every top-level async def that runs as a cron task
    or loop should document what it does, so operators and future
    maintainers can reason about the system without reading every line.
    """

    FUNCTIONS_TO_CHECK = [
        ("jobs.cron.trial_risk_detection", "detect_at_risk_trials"),
        ("jobs.cron.new_bids_notifier", "run_new_bids_notifier"),
        ("jobs.cron.indice_municipal", "run_indice_municipal_recalc"),
        ("jobs.cron.auth_cleanup", "run_auth_cleanup_once"),
        ("jobs.cron.auth_cleanup", "reset_stale_auth_attempts"),
        ("jobs.cron.auth_cleanup", "clear_expired_force_mfa"),
        ("jobs.cron.cron_monitor", "run_cron_monitor"),
        ("jobs.cron.cron_monitor", "cron_monitoring_job"),
        ("jobs.cron.cron_monitor", "evaluate_jobs"),
        ("jobs.cron.send_lead_magnet", "send_lead_magnet_job"),
        ("jobs.cron.send_lead_magnet", "send_lead_magnet_batch_job"),
        ("jobs.cron.seo_coverage_manifest", "run_seo_coverage_manifest"),
        ("jobs.cron.metrics_refresh", "run_metrics_refresh_once"),
        ("jobs.cron.competitive_alert_job", "run_competitive_alert_detection"),
        ("jobs.cron.network_events_cleanup", "aggregate_and_cleanup_network_events"),
        ("jobs.cron.founders_auto_disable", "founders_auto_disable_check"),
        ("jobs.cron.subcontract_discovery", "run_subcontract_discovery"),
        ("jobs.cron.monthly_report_job", "run_monthly_report_delivery"),
        ("cron.cache", "_do_cache_cleanup"),
    ]

    @pytest.mark.timeout(10)
    @pytest.mark.parametrize("modname,funcname", FUNCTIONS_TO_CHECK)
    def test_function_has_docstring(self, modname, funcname):
        mod = __import__(modname, fromlist=[funcname])
        func = getattr(mod, funcname, None)
        assert func is not None, f"{modname}.{funcname} not found"
        doc = func.__doc__
        assert doc is not None and len(doc.strip()) > 0, (
            f"{modname}.{funcname} is missing a docstring"
        )


# ──────────────────────────────────────────────────────────────────────
# _next_utc_hour helper tests
# ──────────────────────────────────────────────────────────────────────

class TestNextUtcHour:
    """Tests for the _next_utc_hour helper used by several cron modules.

    All implementations behave identically: calculate seconds until the
    next occurrence of target_hour UTC. Minimum 60s, maximum 86400s.
    """

    @pytest.mark.timeout(10)
    def test_notifications_next_utc_hour_returns_float(self):
        from jobs.cron.notifications import _next_utc_hour
        delay = _next_utc_hour(6)
        assert isinstance(delay, (int, float))
        assert 60.0 <= delay <= 86400.0

    @pytest.mark.timeout(10)
    def test_trial_risk_next_utc_hour_returns_float(self):
        from jobs.cron.trial_risk_detection import _next_utc_hour
        delay = _next_utc_hour(12)
        assert isinstance(delay, (int, float))
        assert 60.0 <= delay <= 86400.0

    @pytest.mark.timeout(10)
    def test_new_bids_next_utc_hour_returns_float(self):
        from jobs.cron.new_bids_notifier import _next_utc_hour
        delay = _next_utc_hour(12)
        assert isinstance(delay, (int, float))
        assert 60.0 <= delay <= 86400.0

    @pytest.mark.timeout(10)
    def test_billing_next_utc_hour_returns_float(self):
        from jobs.cron.billing import _next_utc_hour
        delay = _next_utc_hour(3)
        assert isinstance(delay, (int, float))
        assert 60.0 <= delay <= 86400.0


# ──────────────────────────────────────────────────────────────────────
# Distributed lock mechanics
# ──────────────────────────────────────────────────────────────────────

class TestRedisDistributedLock:
    """Tests for Redis NX lock pattern used by cron jobs.

    Multiple cron modules (billing, notifications, billing_reconciliation,
    api_metered_billing) use a common pattern:
        1. Try redis.set(key, ..., nx=True, ex=TTL)
        2. If returns truthy → proceed (lock acquired)
        3. If returns falsy → skip (lock held by another worker)
        4. finally: redis.delete(key)
    """

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_acquire_lock_happy_path(self):
        """Lock is acquired when Redis is available and key is new."""
        from cron._loop import acquire_redis_lock
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with patch("redis_pool.get_redis_pool", AsyncMock(return_value=mock_redis)):
            acquired = await acquire_redis_lock("test:lock", 60)
            assert acquired is True
            mock_redis.set.assert_called_once()

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_acquire_lock_when_held(self):
        """Lock is NOT acquired when Redis returns None (key exists, NX fails)."""
        from cron._loop import acquire_redis_lock
        mock_redis = AsyncMock()
        mock_redis.set.return_value = None  # NX lock not acquired

        with patch("redis_pool.get_redis_pool", AsyncMock(return_value=mock_redis)):
            acquired = await acquire_redis_lock("test:lock", 60)
            assert acquired is False

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_acquire_lock_redis_unavailable(self):
        """Lock is acquired (fail-open) when Redis raises an error."""
        from cron._loop import acquire_redis_lock
        with patch("redis_pool.get_redis_pool", AsyncMock(side_effect=Exception("Redis down"))):
            acquired = await acquire_redis_lock("test:lock", 60)
            assert acquired is True  # fail-open

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_acquire_lock_redis_none(self):
        """Lock is acquired (fail-open) when get_redis_pool returns None."""
        from cron._loop import acquire_redis_lock
        with patch("redis_pool.get_redis_pool", AsyncMock(return_value=None)):
            acquired = await acquire_redis_lock("test:lock", 60)
            assert acquired is True

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_release_lock(self):
        """Lock is deleted on release."""
        from cron._loop import release_redis_lock
        mock_redis = AsyncMock()

        with patch("redis_pool.get_redis_pool", AsyncMock(return_value=mock_redis)):
            await release_redis_lock("test:lock")
            mock_redis.delete.assert_called_once_with("test:lock")

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_release_lock_redis_unavailable(self):
        """Release does not raise when Redis is unavailable."""
        from cron._loop import release_redis_lock
        with patch("redis_pool.get_redis_pool", AsyncMock(side_effect=Exception("Redis down"))):
            # Should not raise
            await release_redis_lock("test:lock")

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_billing_acquire_lock_helpers(self):
        """Test billing module's _acquire_lock / _release_lock helpers."""
        from jobs.cron.billing import _acquire_lock, _release_lock
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True

        with patch("redis_pool.get_redis_pool", AsyncMock(return_value=mock_redis)):
            acquired = await _acquire_lock("billing:test:lock", 60)
            assert acquired is True

            await _release_lock("billing:test:lock")
            mock_redis.delete.assert_called_with("billing:test:lock")

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_alerts_lock_skip_when_held(self):
        """run_search_alerts returns 'skipped' when lock is held."""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = None  # NX fails

        with (
            patch("redis_pool.get_redis_pool", AsyncMock(return_value=mock_redis)),
            patch("jobs.cron.notifications.ALERTS_ENABLED", True),
        ):
            from jobs.cron.notifications import run_search_alerts
            result = await run_search_alerts()
            assert result["status"] == "skipped"
            assert result["reason"] == "lock_held"


# ──────────────────────────────────────────────────────────────────────
# Mock execution of individual cron jobs
# ──────────────────────────────────────────────────────────────────────

class TestCleanupExpiredResults:
    """Tests for cleanup_expired_results — session_cleanup module."""

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_happy_path(self, mock_execute, mock_get_sb):
        from jobs.cron.session_cleanup import cleanup_expired_results
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.delete.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=[{"id": "1"}, {"id": "2"}])

        result = await cleanup_expired_results()
        assert result["deleted"] == 2
        assert "cleaned_at" in result

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase", side_effect=Exception("DB down"))
    async def test_error_handling(self, mock_get_sb):
        from jobs.cron.session_cleanup import cleanup_expired_results
        result = await cleanup_expired_results()
        assert result["deleted"] == 0
        assert "error" in result


class TestRecordDailyVolume:
    """Tests for record_daily_volume — notifications module."""

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_happy_path(self, mock_execute, mock_get_sb):
        from jobs.cron.notifications import record_daily_volume
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.select.return_value = mock_sb
        mock_sb.gte.return_value = mock_sb
        mock_sb.in_.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=[
            {"total_raw": 100},
            {"total_raw": 50},
        ])

        result = await record_daily_volume()
        assert result["total_bids_24h"] == 150
        assert result["session_count"] == 2

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase", side_effect=Exception("DB down"))
    async def test_error_handling(self, mock_get_sb):
        from jobs.cron.notifications import record_daily_volume
        result = await record_daily_volume()
        assert result["total_bids_24h"] == 0
        assert "error" in result


class TestPurgeOldStripeEvents:
    """Tests for purge_old_stripe_events — billing module."""

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_happy_path(self, mock_execute, mock_get_sb):
        from jobs.cron.billing import purge_old_stripe_events
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.delete.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=[{"id": "evt_1"}, {"id": "evt_2"}, {"id": "evt_3"}])

        result = await purge_old_stripe_events()
        assert result["deleted"] == 3
        assert "cutoff" in result

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase", side_effect=Exception("DB down"))
    async def test_error_handling(self, mock_get_sb):
        from jobs.cron.billing import purge_old_stripe_events
        result = await purge_old_stripe_events()
        assert result["deleted"] == 0
        assert "error" in result


class TestRunAuthCleanupOnce:
    """Tests for run_auth_cleanup_once — auth_cleanup module."""

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_happy_path(self, mock_execute, mock_get_sb):
        from jobs.cron.auth_cleanup import run_auth_cleanup_once
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        # Both auth_attempts and profiles queries
        mock_sb.table.return_value = mock_sb
        mock_sb.update.return_value = mock_sb
        mock_sb.gt.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=[])

        result = await run_auth_cleanup_once()
        assert "attempts" in result
        assert "force_mfa" in result
        assert result["attempts"]["reset"] == 0
        assert result["force_mfa"]["cleared"] == 0

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase", side_effect=Exception("DB down"))
    async def test_error_handling(self, mock_get_sb):
        from jobs.cron.auth_cleanup import run_auth_cleanup_once
        result = await run_auth_cleanup_once()
        # Even on error, the function catches and returns structured result
        assert "attempts" in result
        assert "force_mfa" in result


class TestRunIndiceMunicipalRecalc:
    """Tests for run_indice_municipal_recalc — indice_municipal module."""

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_timeout_returned(self):
        """When _run_with_budget raises TimeoutError, function returns error dict."""
        from jobs.cron.indice_municipal import run_indice_municipal_recalc
        with (
            patch("jobs.cron.indice_municipal._run_with_budget",
                  AsyncMock(side_effect=TimeoutError("budget exceeded"))),
            patch("jobs.cron.indice_municipal.INDICE_MUNICIPAL_DURATION", MagicMock()),
        ):
            result = await run_indice_municipal_recalc()
            assert result["status"] == "error"
            assert "timeout" in result["error"].lower()

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    async def test_success_path(self):
        """Successful recalc returns result dict from the budgeted call."""
        from jobs.cron.indice_municipal import run_indice_municipal_recalc
        fake_result = {"status": "ok", "updated": 42}

        with (
            patch("jobs.cron.indice_municipal._run_with_budget",
                  AsyncMock(return_value=fake_result)),
            patch("jobs.cron.indice_municipal.INDICE_MUNICIPAL_DURATION", MagicMock()),
            patch("email_service.send_email_async", AsyncMock()),
        ):
            result = await run_indice_municipal_recalc()
            assert result == fake_result


# ──────────────────────────────────────────────────────────────────────
# Resilience — empty/missing input handling
# ──────────────────────────────────────────────────────────────────────

class TestCronJobResilience:
    """Cron jobs should never crash when Supabase returns empty data or
    encounters transient errors. Every function must return a structured
    dict on both success and failure paths.

    This is critical: a crashing cron loop kills the background task,
    silencing all downstream monitoring until the next deploy.
    """

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_cleanup_expired_results_empty(self, mock_execute, mock_get_sb):
        """Empty result set does not crash cleanup_expired_results."""
        from jobs.cron.session_cleanup import cleanup_expired_results
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.delete.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=[])

        result = await cleanup_expired_results()
        assert result["deleted"] == 0

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_cleanup_expired_results_none_data(self, mock_execute, mock_get_sb):
        """None data does not crash cleanup_expired_results."""
        from jobs.cron.session_cleanup import cleanup_expired_results
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.delete.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=None)

        result = await cleanup_expired_results()
        assert result["deleted"] == 0

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_new_bids_notifier_empty_profiles(self, mock_execute, mock_get_sb):
        """No active profiles returns structured empty result."""
        from jobs.cron.new_bids_notifier import run_new_bids_notifier
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.select.return_value = mock_sb
        mock_sb.in_.return_value = mock_sb
        mock_sb.not_.is_.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=[])

        result = await run_new_bids_notifier()
        assert result["processed"] == 0

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_trial_risk_empty_users(self, mock_execute, mock_get_sb):
        """No trial users returns structured empty result (not a crash)."""
        from jobs.cron.trial_risk_detection import detect_at_risk_trials
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.select.return_value = mock_sb
        mock_sb.eq.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=[])

        result = await detect_at_risk_trials()
        assert result["total"] == 0
        assert result["errors"] == 0

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_auth_cleanup_empty_results(self, mock_execute, mock_get_sb):
        """Both cleanup steps handle empty results gracefully."""
        from jobs.cron.auth_cleanup import run_auth_cleanup_once
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.update.return_value = mock_sb
        mock_sb.gt.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=[])

        result = await run_auth_cleanup_once()
        assert result["attempts"]["reset"] == 0
        assert result["force_mfa"]["cleared"] == 0

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    @patch("supabase_client.sb_execute", new_callable=AsyncMock)
    async def test_purge_stripe_events_empty(self, mock_execute, mock_get_sb):
        """Purge with no events to delete returns deleted=0."""
        from jobs.cron.billing import purge_old_stripe_events
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.table.return_value = mock_sb
        mock_sb.delete.return_value = mock_sb
        mock_sb.lt.return_value = mock_sb
        mock_execute.return_value = SimpleNamespace(data=None)

        result = await purge_old_stripe_events()
        assert result["deleted"] == 0

    @pytest.mark.timeout(15)
    @pytest.mark.asyncio
    @patch("supabase_client.get_supabase")
    async def test_run_search_alerts_disabled(self, mock_get_sb):
        """When ALERTS_ENABLED is False, returns disabled status."""
        from jobs.cron.notifications import run_search_alerts
        with patch("jobs.cron.notifications.ALERTS_ENABLED", False):
            result = await run_search_alerts()
            assert result["status"] == "disabled"


# ──────────────────────────────────────────────────────────────────────
# Database error classification (is_cb_or_connection_error) across modules
# ──────────────────────────────────────────────────────────────────────

class TestDbErrorDetection:
    """Circuit-breaker / connection error detection in cron modules.

    Every cron module needs to distinguish between:
    - Transient infra errors (CB, connection) → warning, skip, retry
    - Other errors (logic bugs, data issues) → error log + Sentry
    """

    @pytest.mark.timeout(10)
    def test_auth_cleanup_is_cb_or_connection_error(self):
        from jobs.cron.auth_cleanup import _is_cb_or_connection_error as fn
        assert fn(Exception("CircuitBreakerOpenError")) is True
        assert fn(ConnectionError("refused")) is True
        assert fn(TimeoutError("timed out")) is True
        assert fn(ValueError("bad data")) is False

    @pytest.mark.timeout(10)
    def test_metrics_refresh_is_cb_or_connection_error(self):
        from jobs.cron.metrics_refresh import _is_cb_or_connection_error as fn
        assert fn(Exception("circuit open")) is True
        assert fn(ConnectionError("refused")) is True  # name=connectionerror
        assert fn(TimeoutError("timed out")) is True

    @pytest.mark.timeout(10)
    def test_cron_monitor_evaluate_jobs_skip_disabled(self):
        """Disabled jobs (active=False) are excluded from problem list."""
        from jobs.cron.cron_monitor import evaluate_jobs
        now = datetime.now(timezone.utc)
        rows = [
            {"jobname": "healthy-job", "active": True,
             "last_status": "succeeded", "last_run_at": now.isoformat()},
            {"jobname": "disabled-job", "active": False,
             "last_status": "failed", "last_run_at": now.isoformat()},
        ]
        problems = evaluate_jobs(rows, now=now)
        assert len(problems) == 0

    @pytest.mark.timeout(10)
    def test_cron_monitor_evaluate_jobs_failed(self):
        """Jobs with last_status=failed are flagged."""
        from jobs.cron.cron_monitor import evaluate_jobs
        rows = [
            {"jobname": "failing-job", "active": True, "last_status": "failed"},
        ]
        problems = evaluate_jobs(rows)
        assert len(problems) == 1
        assert problems[0]["jobname"] == "failing-job"
        assert problems[0]["reason"] == "last_status=failed"

    @pytest.mark.timeout(10)
    def test_cron_monitor_compute_stale_threshold(self):
        """Schedule-aware stale thresholds."""
        from jobs.cron.cron_monitor import _compute_stale_threshold_hours, STALE_AFTER_HOURS
        # Default (no schedule info) → STALE_AFTER_HOURS
        assert _compute_stale_threshold_hours(None) == STALE_AFTER_HOURS
        # Daily → STALE_AFTER_HOURS
        assert _compute_stale_threshold_hours("0 2 * * *") == STALE_AFTER_HOURS
        # Specific day-of-month → monthly threshold
        monthly = _compute_stale_threshold_hours("0 2 1 * *")
        assert monthly > STALE_AFTER_HOURS
        # Day-of-week → weekly threshold
        weekly = _compute_stale_threshold_hours("30 6 * * 0")
        assert weekly > STALE_AFTER_HOURS


# ──────────────────────────────────────────────────────────────────────
# start_*_task factory sanity
# ──────────────────────────────────────────────────────────────────────

class TestStartTaskFactories:
    """Every start_*_task function should return an asyncio.Task-like object
    with a meaningful name.  We verify the return type and name structure
    without actually running the infinite loop.
    """

    FACTORIES = [
        ("jobs.cron.canary", "start_health_canary_task", "health_canary"),
        ("jobs.cron.session_cleanup", "start_session_cleanup_task", "session_cleanup"),
        ("jobs.cron.session_cleanup", "start_results_cleanup_task", "results_cleanup"),
        ("jobs.cron.notifications", "start_alerts_task", "search_alerts"),
        ("jobs.cron.notifications", "start_trial_sequence_task", "trial_email_sequence"),
        ("jobs.cron.notifications", "start_support_sla_task", "support_sla"),
        ("jobs.cron.notifications", "start_daily_volume_task", "daily_volume"),
        ("jobs.cron.notifications", "start_sector_stats_task", "sector_stats_refresh"),
        ("jobs.cron.billing", "start_reconciliation_task", "stripe_reconciliation"),
        ("jobs.cron.billing", "start_pre_dunning_task", "pre_dunning"),
        ("jobs.cron.billing", "start_revenue_share_task", "revenue_share_report"),
        ("jobs.cron.billing", "start_plan_reconciliation_task", "plan_reconciliation"),
        ("jobs.cron.billing", "start_stripe_events_purge_task", "stripe_events_purge"),
        ("jobs.cron.cron_monitor", "start_cron_monitor_task", "cron_monitor"),
        ("jobs.cron.pncp_canary", "start_pncp_canary_task", "pncp_canary"),
        ("jobs.cron.llm_batch_poll", "start_llm_batch_poll_task", "llm_batch_poll"),
        ("jobs.cron.auth_cleanup", "start_auth_cleanup_task", "auth_cleanup"),
        ("jobs.cron.metrics_refresh", "start_metrics_refresh_task", "metrics_refresh"),
    ]

    @pytest.mark.timeout(10)
    @pytest.mark.parametrize("modname,funcname,expected_name_prefix", FACTORIES)
    @pytest.mark.asyncio
    async def test_factory_returns_task_with_name(self, modname, funcname, expected_name_prefix):
        mod = __import__(modname, fromlist=[funcname])
        factory = getattr(mod, funcname)
        task = await factory()
        assert task is not None
        assert expected_name_prefix in task.get_name()

    @pytest.mark.timeout(10)
    @pytest.mark.asyncio
    async def test_seo_snapshot_factory(self):
        from jobs.cron.seo_snapshot import start_seo_snapshot_task
        task = await start_seo_snapshot_task()
        assert task is not None

    @pytest.mark.timeout(10)
    @pytest.mark.asyncio
    async def test_indice_municipal_factory(self):
        from jobs.cron.indice_municipal import start_indice_municipal_task
        task = await start_indice_municipal_task()
        assert task is not None
        assert "indice_municipal" in task.get_name()

    @pytest.mark.timeout(10)
    @pytest.mark.asyncio
    async def test_new_bids_notifier_factory(self):
        from jobs.cron.new_bids_notifier import start_new_bids_notifier_task
        task = await start_new_bids_notifier_task()
        assert task is not None
        assert "new_bids_notifier" in task.get_name()

    @pytest.mark.timeout(10)
    @pytest.mark.asyncio
    async def test_billing_reconciliation_factory(self):
        from jobs.cron.billing_reconciliation import start_billing_reconciliation_task
        task = await start_billing_reconciliation_task()
        assert task is not None
        assert "billing_reconciliation" in task.get_name()

    @pytest.mark.timeout(10)
    @pytest.mark.asyncio
    async def test_seo_coverage_manifest_factory(self):
        from jobs.cron.seo_coverage_manifest import start_seo_coverage_manifest_task
        task = await start_seo_coverage_manifest_task()
        assert task is not None
        assert "seo_coverage_manifest" in task.get_name()

    @pytest.mark.timeout(10)
    @pytest.mark.asyncio
    async def test_lead_magnet_batch_factory(self):
        from jobs.cron.send_lead_magnet import start_lead_magnet_batch_task
        task = await start_lead_magnet_batch_task()
        assert task is not None

    @pytest.mark.timeout(10)
    @pytest.mark.asyncio
    async def test_trial_risk_factory(self):
        from jobs.cron.trial_risk_detection import start_trial_risk_task
        task = await start_trial_risk_task()
        assert task is not None
        assert "trial_risk" in task.get_name()

    @pytest.mark.timeout(10)
    @pytest.mark.asyncio
    async def test_cache_cleanup_factory(self):
        from cron.cache import start_cache_cleanup_task
        task = await start_cache_cleanup_task()
        assert task is not None
        assert "cache_cleanup" in task.get_name()

    @pytest.mark.timeout(10)
    @pytest.mark.asyncio
    async def test_register_all_cron_tasks(self):
        """Every task factory in register_all_cron_tasks returns asyncio.Task."""
        from jobs.cron.scheduler import register_all_cron_tasks
        factories = register_all_cron_tasks()
        assert len(factories) > 0
        for factory in factories:
            task = await factory()
            assert task is not None


# ──────────────────────────────────────────────────────────────────────
# canary helpers
# ──────────────────────────────────────────────────────────────────────

class TestCanaryHelpers:
    """Unit tests for canary helper functions."""

    @pytest.mark.timeout(10)
    def test_get_pncp_cron_status_returns_copy(self):
        """Status getter returns a copy, not the internal dict."""
        import cron_jobs
        status = get_pncp_cron_status()
        status["custom"] = "injected"
        with cron_jobs._pncp_cron_status_lock:
            assert "custom" not in cron_jobs._pncp_cron_status

    @pytest.mark.timeout(10)
    def test_get_pncp_recovery_epoch_returns_int(self):
        epoch = get_pncp_recovery_epoch()
        assert isinstance(epoch, int)

    @pytest.mark.timeout(10)
    def test_canary_constant(self):
        from jobs.cron.canary import HEALTH_CANARY_INTERVAL_SECONDS
        assert HEALTH_CANARY_INTERVAL_SECONDS > 0


# ──────────────────────────────────────────────────────────────────────
# cron._loop helpers
# ──────────────────────────────────────────────────────────────────────

class TestCronLoopHelpers:
    """Unit tests for the shared cron loop runner."""

    @pytest.mark.timeout(10)
    def test_is_cb_or_connection_error_loop(self):
        from cron._loop import is_cb_or_connection_error
        assert is_cb_or_connection_error(
            type("CircuitBreakerError", (Exception,), {})("open")
        ) is True
        assert is_cb_or_connection_error(ConnectionError("refused")) is True
        assert is_cb_or_connection_error(Exception("PGRST205: schema")) is True
        assert is_cb_or_connection_error(Exception("ConnectError: timeout")) is True
        assert is_cb_or_connection_error(ValueError("bad")) is False

    @pytest.mark.timeout(10)
    def test_is_cb_or_connection_error_from_cron_jobs(self):
        """The re-exported version in cron_jobs should match."""
        from cron_jobs import _is_cb_or_connection_error as cj_check
        assert cj_check(ConnectionError("timeout")) is True
        assert cj_check(RuntimeError("bug")) is False
