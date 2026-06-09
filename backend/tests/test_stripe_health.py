"""DEC-BIL-GAP-02: Tests for Stripe health check service.

Coverage:
- Stripe online → {"stripe": "ok"}
- Strip offline < 4h → grace period, no notification
- Stripe offline > 4h → notification sent
- Recovery after offline
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures — reset in-memory state before each test
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_stripe_health_state():
    """Reset in-memory state between tests to avoid cross-test pollution."""
    import services.stripe_health as sh

    sh._inmemory_fail_since = None
    sh._inmemory_last_notification = None
    sh._inmemory_cached_status = None
    sh._inmemory_cache_ts = 0.0


@pytest.fixture
def mock_stripe_configured():
    """Patch STRIPE_SECRET_KEY so _stripe_configured() returns True."""
    with patch("os.getenv", return_value="sk_test_xxx"):
        yield


@pytest.fixture
def mock_account_retrieve():
    """Patch stripe.Account.retrieve to succeed."""
    with patch("stripe.Account.retrieve") as mock:
        yield mock


@pytest.fixture
def mock_send_email():
    """Patch send_email_async (imported locally in _send_founder_notification)."""
    with patch("email_service.send_email_async") as mock:
        yield mock


@pytest.fixture
def mock_sentry():
    """Patch sentry_sdk.capture_message."""
    with patch("sentry_sdk.capture_message") as mock:
        yield mock


@pytest.fixture
def mock_redis_none():
    """Make _get_redis return None (no Redis available)."""
    with patch("services.stripe_health._get_redis", return_value=None):
        yield


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.asyncio
async def test_stripe_online(
    mock_stripe_configured,
    mock_account_retrieve,
    mock_redis_none,
):
    """Stripe online → {"stripe": "ok"}."""
    from services.stripe_health import get_stripe_health

    result = await get_stripe_health()
    assert result == {"stripe": "ok"}


@pytest.mark.asyncio
async def test_stripe_offline_within_grace(
    mock_stripe_configured,
    mock_account_retrieve,
    mock_redis_none,
    mock_send_email,
    mock_sentry,
):
    """Stripe offline < 4h → grace period, no notification."""
    from services.stripe_health import get_stripe_health

    # Make Account.retrieve fail
    mock_account_retrieve.side_effect = Exception("Connection refused")

    result = await get_stripe_health()

    assert result["stripe"] == "unreachable"
    assert "since" in result
    assert result["grace_period_hours"] == 4
    assert "grace_remaining_hours" in result
    assert 3.5 < result["grace_remaining_hours"] <= 4.0
    assert "notified" not in result

    # Verify no notification was sent
    mock_send_email.assert_not_called()
    mock_sentry.assert_called_once()


@pytest.mark.asyncio
async def test_stripe_offline_beyond_grace(
    mock_stripe_configured,
    mock_account_retrieve,
    mock_redis_none,
    mock_send_email,
    mock_sentry,
):
    """Stripe offline > 4h → notification sent."""
    from services.stripe_health import get_stripe_health

    # Make Account.retrieve fail
    mock_account_retrieve.side_effect = Exception("Connection refused")

    # Simulate first call to set fail_since with a far-past timestamp
    import services.stripe_health as sh

    # Override fail_since to ~5 hours ago
    past_time = time.monotonic() - (5 * 3600)
    sh._set_fail_since(past_time)

    result = await get_stripe_health()

    assert result["stripe"] == "unreachable"
    assert result["notified"] is True
    assert "grace_remaining_hours" not in result  # grace expired

    # Verify notification was sent
    mock_send_email.assert_called_once()
    call_args = mock_send_email.call_args
    assert call_args is not None
    kwargs = call_args[1]
    assert "tiago.sasaki@gmail.com" in kwargs.get("to", "")
    assert "Stripe offline" in kwargs.get("subject", "")


@pytest.mark.asyncio
async def test_recovery_after_offline(
    mock_stripe_configured,
    mock_account_retrieve,
    mock_redis_none,
    mock_send_email,
    mock_sentry,
):
    """Stripe offline then recovery → {"stripe": "ok"} and state cleared."""
    from services.stripe_health import get_stripe_health

    import services.stripe_health as sh

    # Simulate Stripe offline first
    mock_account_retrieve.side_effect = Exception("Connection refused")
    past_time = time.monotonic() - (5 * 3600)
    sh._set_fail_since(past_time)

    result = await get_stripe_health()
    assert result["stripe"] == "unreachable"
    assert result.get("notified") is True

    # Now simulate Stripe recovered
    mock_account_retrieve.side_effect = None  # Remove exception
    # Clear in-memory cache so check_stripe_connection probes again
    sh._inmemory_cached_status = None
    sh._inmemory_cache_ts = 0.0

    result = await get_stripe_health()
    assert result == {"stripe": "ok"}

    # Verify in-memory state was cleared
    assert sh._get_fail_since() is None
    assert sh._get_last_notification() is None


@pytest.mark.asyncio
async def test_stripe_not_configured():
    """No STRIPE_SECRET_KEY → {"stripe": "ok"} (dev mode)."""
    with patch("os.getenv", return_value=None):
        from services.stripe_health import get_stripe_health

        result = await get_stripe_health()
        assert result == {"stripe": "ok"}


@pytest.mark.asyncio
async def test_notification_cooldown(
    mock_stripe_configured,
    mock_account_retrieve,
    mock_redis_none,
    mock_send_email,
    mock_sentry,
):
    """Second check within cooldown → no duplicate notification."""
    from services.stripe_health import get_stripe_health

    import services.stripe_health as sh

    mock_account_retrieve.side_effect = Exception("Connection refused")
    past_time = time.monotonic() - (5 * 3600)
    sh._set_fail_since(past_time)

    # First call — should notify
    result1 = await get_stripe_health()
    assert result1["notified"] is True
    assert mock_send_email.call_count == 1

    # Second call immediately — should NOT notify again (cooldown)
    # but 'notified' is still True because grace period already elapsed
    result2 = await get_stripe_health()
    assert result2["notified"] is True
    assert mock_send_email.call_count == 1  # Still 1 — cooldown prevented second notification


@pytest.mark.asyncio
async def test_in_memory_cache(
    mock_stripe_configured,
    mock_account_retrieve,
    mock_redis_none,
):
    """60s cache avoids redundant Stripe API calls."""
    from services.stripe_health import check_stripe_connection

    # First call — probes Stripe
    with patch("services.stripe_health.time.monotonic") as mock_time:
        mock_time.return_value = 0.0
        result1 = await check_stripe_connection()
        assert result1 is True
        assert mock_account_retrieve.call_count == 1

    # Second call within 60s — uses cache
    with patch("services.stripe_health.time.monotonic") as mock_time:
        mock_time.return_value = 30.0  # 30s later
        result2 = await check_stripe_connection()
        assert result2 is True
        assert mock_account_retrieve.call_count == 1  # No new call


@pytest.mark.asyncio
async def test_health_route_returns_ok(
    mock_stripe_configured,
    mock_account_retrieve,
    mock_redis_none,
):
    """GET /v1/health/stripe returns 200 when Stripe is ok."""
    from services.stripe_health import get_stripe_health

    result = await get_stripe_health()
    assert result == {"stripe": "ok"}


@pytest.mark.asyncio
async def test_health_route_returns_503(
    mock_stripe_configured,
    mock_account_retrieve,
    mock_redis_none,
):
    """GET /v1/health/stripe returns 503 when Stripe is unreachable."""
    from services.stripe_health import get_stripe_health

    mock_account_retrieve.side_effect = Exception("Connection refused")
    import services.stripe_health as sh

    past_time = time.monotonic() - (5 * 3600)
    sh._set_fail_since(past_time)

    with patch("services.stripe_health._send_founder_notification"):
        result = await get_stripe_health()

    assert result["stripe"] == "unreachable"
