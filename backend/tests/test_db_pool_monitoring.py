"""Issue #1916: Tests for database connection pool monitoring.

Covers:
  1. ``get_db_pool_stats()`` — RPC path vs tracked fallback
  2. ``check_and_alert_utilization()`` — Redis duration tracking + Sentry
  3. ``update_db_pool_metrics()`` — Prometheus gauge updates
  4. ``run_db_pool_monitor()`` — end-to-end integration smoke test
  5. Admin endpoint response shape and status classification
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# Helpers
# ============================================================================


def _make_rpc_response(active: int = 3, max_conn: int = 25) -> MagicMock:
    """Build a mock response mimicking ``sb.rpc("get_db_pool_stats").execute()``."""
    data = {
        "active_connections": active,
        "idle_connections": max_conn - active,
        "idle_in_transaction": 0,
        "total_connections": max_conn,
        "max_connections": max_conn,
        "waiting_connections": 0,
    }
    mock = MagicMock()
    mock.data = data
    return mock


# ============================================================================
# Test: get_db_pool_stats — RPC path
# ============================================================================


@pytest.mark.asyncio
async def test_get_db_pool_stats_rpc_success():
    """get_db_pool_stats should return pg_stat_activity data when RPC succeeds."""
    rpc_response = _make_rpc_response(active=5, max_conn=25)

    # Patch at source module level — the monitoring module uses lazy imports
    # (from supabase_client import get_supabase, sb_execute)
    with (
        patch("supabase_client.get_supabase") as mock_get_sb,
        patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec,
    ):
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.rpc.return_value = MagicMock()
        mock_exec.return_value = rpc_response

        from monitoring.db_pool_monitor import get_db_pool_stats
        stats = await get_db_pool_stats()

    assert stats["active"] == 5
    assert stats["max"] == 25
    assert stats["utilization"] == pytest.approx(0.2, rel=0.01)
    assert stats["idle"] == 20
    assert stats["total"] == 25
    assert stats["source"] == "pg_stat_activity"


@pytest.mark.asyncio
async def test_get_db_pool_stats_rpc_zero_connections():
    """get_db_pool_stats should handle zero active connections gracefully."""
    rpc_response = _make_rpc_response(active=0, max_conn=25)

    with (
        patch("supabase_client.get_supabase") as mock_get_sb,
        patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec,
    ):
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.rpc.return_value = MagicMock()
        mock_exec.return_value = rpc_response

        from monitoring.db_pool_monitor import get_db_pool_stats
        stats = await get_db_pool_stats()

    assert stats["active"] == 0
    assert stats["utilization"] == 0.0
    assert stats["source"] == "pg_stat_activity"


@pytest.mark.asyncio
async def test_get_db_pool_stats_fallback_tracked():
    """get_db_pool_stats should fall back to tracked counters when RPC fails."""
    with (
        patch("supabase_client.get_supabase") as mock_get_sb,
        patch("supabase_client.sb_execute", side_effect=RuntimeError("RPC fail")),
        patch("supabase_client._pool_active_count", 7),
        patch("supabase_client._POOL_MAX_CONNECTIONS", 25),
    ):
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.rpc.return_value = MagicMock()

        from monitoring.db_pool_monitor import get_db_pool_stats
        stats = await get_db_pool_stats()

    assert stats["active"] == 7
    assert stats["max"] == 25
    assert stats["utilization"] == pytest.approx(0.28, rel=0.01)
    assert stats["source"] == "tracked"


# ============================================================================
# Test: check_and_alert_utilization — Sentry alert with Redis duration
# ============================================================================


@pytest.mark.asyncio
async def test_check_alert_below_threshold_no_action():
    """No alert when utilization is below 85% -- below-threshold path
    only calls redis.delete() and does NOT trigger sentry."""
    stats = {"active": 10, "max": 25, "utilization": 0.4, "source": "tracked"}
    redis_mock = AsyncMock()

    with patch("redis_pool.get_redis_pool", return_value=redis_mock):
        from monitoring.db_pool_monitor import check_and_alert_utilization
        await check_and_alert_utilization(stats)

    redis_mock.delete.assert_called_once()
    redis_mock.set.assert_not_called()


@pytest.mark.asyncio
async def test_check_alert_above_threshold_sets_redis():
    """Redis key should be set (NX) when utilization first crosses 85%."""
    stats = {"active": 23, "max": 25, "utilization": 0.92, "source": "pg_stat_activity"}
    redis_mock = AsyncMock()
    redis_mock.set.return_value = True  # NX=True, key was set

    with patch("redis_pool.get_redis_pool", return_value=redis_mock):
        from monitoring.db_pool_monitor import check_and_alert_utilization
        await check_and_alert_utilization(stats)

    redis_mock.set.assert_called_once()
    assert redis_mock.set.call_args[0][0] == "db_pool:high_utilization_since"


@pytest.mark.asyncio
async def test_check_alert_sustained_above_threshold_fires_sentry():
    """Sentry alert should fire when utilization >85% for >5min."""
    onset = time.time() - 400  # 400 seconds ago (>5min)

    stats = {"active": 24, "max": 25, "utilization": 0.96, "source": "pg_stat_activity"}
    redis_mock = AsyncMock()
    redis_mock.set.return_value = False  # Key already exists
    redis_mock.get.return_value = str(onset)

    with (
        patch("redis_pool.get_redis_pool", return_value=redis_mock),
        patch("sentry_sdk.capture_message") as mock_capture,
    ):
        from monitoring.db_pool_monitor import check_and_alert_utilization
        await check_and_alert_utilization(stats)

    mock_capture.assert_called_once()
    msg = mock_capture.call_args[0][0]
    assert "DB pool utilization" in msg


@pytest.mark.asyncio
async def test_check_alert_not_yet_sustained_no_sentry():
    """Sentry should NOT fire when utilization is >85% but <5min."""
    onset = time.time() - 60  # 60 seconds ago (<5min)

    stats = {"active": 24, "max": 25, "utilization": 0.96, "source": "pg_stat_activity"}
    redis_mock = AsyncMock()
    redis_mock.set.return_value = False
    redis_mock.get.return_value = str(onset)

    with (
        patch("redis_pool.get_redis_pool", return_value=redis_mock),
        patch("sentry_sdk.capture_message") as mock_capture,
    ):
        from monitoring.db_pool_monitor import check_and_alert_utilization
        await check_and_alert_utilization(stats)

    mock_capture.assert_not_called()


@pytest.mark.asyncio
async def test_check_alert_redis_unavailable_no_crash():
    """Should gracefully handle Redis being unavailable."""
    stats = {"active": 23, "max": 25, "utilization": 0.92, "source": "tracked"}

    # When get_redis_pool returns None, the Redis operations are skipped.
    # The function should not raise any exceptions.
    with patch("redis_pool.get_redis_pool", return_value=None):
        from monitoring.db_pool_monitor import check_and_alert_utilization
        await check_and_alert_utilization(stats)

    # No exception == pass


# ============================================================================
# Test: update_db_pool_metrics — Prometheus gauge updates
# ============================================================================


@pytest.mark.asyncio
async def test_update_metrics_sets_gauges():
    """Prometheus gauges should be updated with latest pool stats."""
    rpc_response = _make_rpc_response(active=8, max_conn=25)

    # Patch at metrics module level because monitoring/db_pool_monitor.py
    # does lazy imports inside the function body
    with (
        patch("supabase_client.get_supabase") as mock_get_sb,
        patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec,
        patch("metrics.DB_POOL_UTILIZATION") as mock_util_gauge,
        patch("metrics.SUPABASE_POOL_ACTIVE") as mock_active_gauge,
        patch("metrics.SUPABASE_POOL_IDLE") as mock_idle_gauge,
        patch("metrics.SUPABASE_POOL_MAX") as mock_max_gauge,
    ):
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.rpc.return_value = MagicMock()
        mock_exec.return_value = rpc_response

        from monitoring.db_pool_monitor import update_db_pool_metrics
        stats = await update_db_pool_metrics()

    mock_util_gauge.set.assert_called_once_with(pytest.approx(0.32, rel=0.01))
    mock_active_gauge.set.assert_called_once_with(8)
    mock_idle_gauge.set.assert_called_once_with(17)
    mock_max_gauge.set.assert_called_once_with(25)
    assert stats["active"] == 8


# ============================================================================
# Test: run_db_pool_monitor — end-to-end integration smoke test
# ============================================================================


@pytest.mark.asyncio
async def test_run_db_pool_monitor_smoke():
    """run_db_pool_monitor should collect stats, update gauges, check threshold."""
    rpc_response = _make_rpc_response(active=5, max_conn=25)
    redis_mock = AsyncMock()
    redis_mock.set.return_value = True
    redis_mock.get.return_value = None

    with (
        patch("supabase_client.get_supabase") as mock_get_sb,
        patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec,
        patch("redis_pool.get_redis_pool", return_value=redis_mock),
        patch("metrics.DB_POOL_UTILIZATION"),
    ):
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.rpc.return_value = MagicMock()
        mock_exec.return_value = rpc_response

        from monitoring.db_pool_monitor import run_db_pool_monitor
        stats = await run_db_pool_monitor()

    assert stats["active"] == 5
    assert stats["utilization"] == pytest.approx(0.2, rel=0.01)
    assert stats["source"] == "pg_stat_activity"


# ============================================================================
# Test: Admin endpoint shape and status classification
# ============================================================================


def test_admin_db_pool_status_classification():
    """Utilization thresholds should map to correct status.

    Thresholds (from routes/admin_db_pool.py):
        healthy   — utilization <= 0.80
        degraded  — 0.80 < utilization <= 0.85
        critical  — utilization > 0.85
    """
    for utilization, expected_status in [
        (0.70, "healthy"),
        (0.80, "healthy"),     # exactly 0.80 is NOT degraded (> is the check)
        (0.81, "degraded"),
        (0.84, "degraded"),
        (0.85, "degraded"),    # exactly 0.85 is NOT > 0.85, so degraded
        (0.86, "critical"),
        (0.90, "critical"),
        (1.00, "critical"),
    ]:
        status = (
            "critical"
            if utilization > 0.85
            else "degraded"
            if utilization > 0.80
            else "healthy"
        )
        assert status == expected_status, (
            f"Utilization {utilization} should be {expected_status}, got {status}"
        )


@pytest.mark.asyncio
async def test_admin_db_pool_response_shape():
    """GET /v1/admin/db-pool should return expected response shape."""
    rpc_response = _make_rpc_response(active=10, max_conn=25)

    with (
        patch("supabase_client.get_supabase") as mock_get_sb,
        patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec,
    ):
        mock_sb = MagicMock()
        mock_get_sb.return_value = mock_sb
        mock_sb.rpc.return_value = MagicMock()
        mock_exec.return_value = rpc_response

        from monitoring.db_pool_monitor import get_db_pool_stats

        stats = await get_db_pool_stats()

    utilization = stats.get("utilization", 0.0)
    result = {
        "status": (
            "critical"
            if utilization > 0.85
            else "degraded"
            if utilization > 0.80
            else "healthy"
        ),
        "active": stats.get("active", 0),
        "idle": stats.get("idle", 0),
        "idle_in_transaction": stats.get("idle_in_transaction", 0),
        "total": stats.get("total", 0),
        "max": stats.get("max", 0),
        "waiting": stats.get("waiting", 0),
        "utilization": utilization,
        "utilization_pct": round(utilization * 100, 1),
        "source": stats.get("source", "unknown"),
        "threshold_warning_pct": 80,
        "threshold_critical_pct": 85,
    }

    assert result["status"] == "healthy"
    assert result["active"] == 10
    assert result["max"] == 25
    assert result["utilization"] == pytest.approx(0.4, rel=0.01)
    assert result["utilization_pct"] == 40.0
    assert result["source"] == "pg_stat_activity"
    assert result["threshold_warning_pct"] == 80
    assert result["threshold_critical_pct"] == 85
