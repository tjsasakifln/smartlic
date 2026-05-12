"""SEN-BE-003 AC3: Tests for DLQ scan graceful skip on Supabase circuit breaker OPEN.

Verifies that reprocess_pending():
1. Logs INFO (not ERROR) when CircuitBreakerOpenError is raised
2. Returns empty stats dict (all zeros)
3. Still logs ERROR for non-CB exceptions (regression guard)
"""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.trial_email_dlq import reprocess_pending


@pytest.mark.asyncio
async def test_reprocess_pending_cb_open_logs_info_not_error(caplog):
    """AC3: CircuitBreakerOpenError must log INFO, not ERROR."""
    caplog.set_level(logging.INFO)

    cb_open_error = __import__("supabase_client").CircuitBreakerOpenError(
        "test_category",
        "Circuit breaker is OPEN",
    )

    with patch("services.trial_email_dlq.sb_execute", side_effect=cb_open_error):
        with patch("services.trial_email_dlq.get_supabase", return_value=MagicMock()):
            stats = await reprocess_pending()

    # Must be empty/all-zero stats
    assert stats == {"considered": 0, "reprocessed": 0, "retried": 0, "abandoned": 0}

    # Must have an INFO record about CB being open
    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert any(
        "circuit breaker" in (r.getMessage() or "").lower() or "cb" in (r.getMessage() or "").lower()
        for r in info_records
    ), "Expected an INFO log mentioning circuit breaker open"

    # Must NOT have an ERROR record
    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert not error_records, f"Expected no ERROR logs but got: {[r.getMessage() for r in error_records]}"


@pytest.mark.asyncio
async def test_reprocess_pending_cb_open_returns_empty_stats():
    """AC3: On CircuitBreakerOpenError, must return empty stats (all zeros)."""
    cb_open_error = __import__("supabase_client").CircuitBreakerOpenError(
        "read",
        "Circuit breaker is OPEN for read",
    )

    with patch("services.trial_email_dlq.sb_execute", side_effect=cb_open_error):
        with patch("services.trial_email_dlq.get_supabase", return_value=MagicMock()):
            stats = await reprocess_pending()

    assert isinstance(stats, dict)
    assert all(v == 0 for v in stats.values()), f"Expected all-zero stats, got {stats}"


@pytest.mark.asyncio
async def test_reprocess_pending_other_error_still_logs_error(caplog):
    """AC3 (regression): Non-CB exceptions must still log as ERROR."""
    caplog.set_level(logging.ERROR)

    other_error = RuntimeError("Something went wrong in the database")

    with patch("services.trial_email_dlq.sb_execute", side_effect=other_error):
        with patch("services.trial_email_dlq.get_supabase", return_value=MagicMock()):
            stats = await reprocess_pending()

    assert stats == {"considered": 0, "reprocessed": 0, "retried": 0, "abandoned": 0}

    error_records = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert any("DLQ scan failed" in (r.getMessage() or "") for r in error_records), (
        "Expected an ERROR log for non-CB exceptions"
    )
