"""#1877: Tests for data retention enhancements — dry-run, admin dashboard, Sentry alert.

Covers:
1. Dry-run mode does not DELETE, only logs (#1877 AC1).
2. Admin status endpoint returns expected shape (#1877 AC2).
3. Consecutive failure tracking alerts Sentry at >=2 failures (#1877 AC3).
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_fake")
os.environ.setdefault("DATA_RETENTION_DRY_RUN", "true")

from main import app  # noqa: E402
from auth import require_auth  # noqa: E402
from admin import require_admin_ops  # noqa: E402
from jobs.cron import data_retention  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_client():
    """TestClient with admin auth override."""
    fake_admin = {"id": "00000000-0000-0000-0000-00000000a001", "email": "admin@test"}
    app.dependency_overrides[require_auth] = lambda: fake_admin
    app.dependency_overrides[require_admin_ops] = lambda: fake_admin
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)
    app.dependency_overrides.pop(require_admin_ops, None)


@pytest.fixture
def regular_client():
    """Logged-in non-admin user — should get 403 from require_admin."""
    fake_user = {"id": "regular-user", "email": "user@test"}
    app.dependency_overrides[require_auth] = lambda: fake_user
    yield TestClient(app)
    app.dependency_overrides.pop(require_auth, None)


@pytest.fixture(autouse=True)
def _clear_dry_run_flag():
    """Ensure DATA_RETENTION_DRY_RUN is set to true for all tests.

    Individual tests can override by patching the module constant.
    """
    original = data_retention.DATA_RETENTION_DRY_RUN
    data_retention.DATA_RETENTION_DRY_RUN = True
    yield
    data_retention.DATA_RETENTION_DRY_RUN = original


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dry_run_skips_delete_trial_email_log():
    """AC1: Dry-run must log and skip actual DELETE for trial_email_log."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.delete.return_value.lt.return_value = "would_query"

    with (
        patch("supabase_client.get_supabase", return_value=mock_sb),
        patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec,
    ):
        result = await data_retention.purge_trial_email_log()

    # sb_execute must NOT be called in dry-run mode
    mock_exec.assert_not_called()
    assert result["deleted"] == 0
    assert result.get("dry_run") is True
    assert result["table"] == "trial_email_log"


@pytest.mark.asyncio
async def test_dry_run_skips_delete_messages():
    """AC1: Dry-run must log and skip actual DELETE for messages."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.delete.return_value.lt.return_value = "would_query"

    with (
        patch("supabase_client.get_supabase", return_value=mock_sb),
        patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec,
    ):
        result = await data_retention.purge_messages()

    mock_exec.assert_not_called()
    assert result["deleted"] == 0
    assert result.get("dry_run") is True
    assert result["table"] == "messages"


@pytest.mark.asyncio
async def test_dry_run_skips_delete_ingestion_checkpoints():
    """AC1: Dry-run must log and skip actual DELETE for ingestion_checkpoints."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.delete.return_value.in_.return_value.lt.return_value = "would_query"

    with (
        patch("supabase_client.get_supabase", return_value=mock_sb),
        patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec,
    ):
        result = await data_retention.purge_ingestion_checkpoints()

    mock_exec.assert_not_called()
    assert result["deleted"] == 0
    assert result.get("dry_run") is True
    assert result["table"] == "ingestion_checkpoints"


def test_admin_status_endpoint_returns_expected_shape(admin_client):
    """AC2: Admin status endpoint returns expected JSON structure."""
    mock_redis = AsyncMock()
    # Simulate Redis with some data
    mock_redis.get = AsyncMock(side_effect=lambda key: {
        "data_retention:last_run:trial_email_log": "2026-06-15T12:00:00",
        "data_retention:last_rows:trial_email_log": "42",
        "data_retention:last_run:messages": "2026-06-15T12:00:00",
        "data_retention:last_rows:messages": "10",
        "data_retention:last_run:ingestion_checkpoints": "2026-06-15T12:00:00",
        "data_retention:last_rows:ingestion_checkpoints": "5",
        "data_retention:last_duration": "3.14",
    }.get(key, None))

    with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis):
        response = admin_client.get("/v1/admin/data-retention/status")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "queried_at" in body
    assert len(body["tables"]) == 3
    assert body["total_rows_purged_last"] == 57  # 42 + 10 + 5
    assert body["last_cycle_duration_seconds"] == 3.14

    # Verify per-table structure
    trial_email = body["tables"][0]
    assert trial_email["name"] == "trial_email_log"
    assert trial_email["rows_purged_last"] == 42
    assert trial_email["last_purge_at"] == "2026-06-15T12:00:00"
    assert trial_email["status"] == "success"


def test_admin_status_endpoint_requires_auth(regular_client):
    """AC2: Non-admin users get 403 from status endpoint."""
    response = regular_client.get("/v1/admin/data-retention/status")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_consecutive_failure_alert_at_threshold():
    """AC3: Sentry alert when consecutive failures >= 2.

    Simulates one error result and one clean result to verify the counter
    only fires at >=2.
    """
    mock_redis = AsyncMock()
    mock_redis.incr = AsyncMock(return_value=2)  # Second consecutive failure
    mock_redis.expire = AsyncMock(return_value=True)

    mock_scope = MagicMock()

    with (
        patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis),
        patch("sentry_sdk.push_scope", return_value=mock_scope),
        patch("sentry_sdk.capture_message") as mock_capture,
    ):
        results = [
            {"table": "trial_email_log", "deleted": 0, "error": "test error"},
            {"table": "messages", "deleted": 0, "error": "test error"},
            {"table": "ingestion_checkpoints", "deleted": 0, "error": "test error"},
        ]
        await data_retention._track_consecutive_failures(results)

    # Should have triggered sentry capture_message
    mock_capture.assert_called_once()
    call_args = mock_capture.call_args
    assert "failed 2x consecutively" in call_args[0][0]
    assert call_args[1]["level"] == "error"


@pytest.mark.asyncio
async def test_consecutive_failure_no_alert_below_threshold():
    """AC3: No Sentry alert when consecutive failures < 2.

    Simulates a clean run (no errors) to verify counter resets to 0.
    """
    mock_redis = AsyncMock()
    mock_redis.set = AsyncMock(return_value=True)
    mock_redis.expire = AsyncMock(return_value=True)

    with (
        patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=mock_redis),
        patch("sentry_sdk.capture_message") as mock_capture,
    ):
        results = [
            {"table": "trial_email_log", "deleted": 10},
            {"table": "messages", "deleted": 5},
            {"table": "ingestion_checkpoints", "deleted": 3},
        ]
        await data_retention._track_consecutive_failures(results)

    # Counter should have been reset to 0 — no sentry alert
    mock_capture.assert_not_called()
    mock_redis.set.assert_called_with("data_retention:consecutive_failures", 0)


@pytest.mark.asyncio
async def test_dry_run_flag_off_deletes_normally():
    """AC1: When dry-run is False, DELETE queries are executed."""
    # Temporarily disable dry-run
    original = data_retention.DATA_RETENTION_DRY_RUN
    data_retention.DATA_RETENTION_DRY_RUN = False

    mock_result = MagicMock()
    mock_result.data = [{"id": 1}, {"id": 2}, {"id": 3}]

    mock_sb = MagicMock()
    mock_sb.table.return_value.delete.return_value.lt.return_value = "query"

    try:
        with (
            patch("supabase_client.get_supabase", return_value=mock_sb),
            patch("supabase_client.sb_execute", new_callable=AsyncMock, return_value=mock_result),
            patch("redis_pool.get_redis_pool", new_callable=AsyncMock) as mock_redis_pool,
        ):
            mock_redis = AsyncMock()
            mock_redis_pool.return_value = mock_redis
            result = await data_retention.purge_trial_email_log()

        assert result["deleted"] == 3
        assert result.get("dry_run") is None
    finally:
        data_retention.DATA_RETENTION_DRY_RUN = original
