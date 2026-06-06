"""Tests for API-SELF-003 — API key rate limiting via Redis monthly counter.

Acceptance criteria:
  - Token bucket Redis por key_id
  - Limits: Starter 1k, Pro 10k, Scale 100k requests/month
  - X-RateLimit-Remaining header on every response
  - Excedeu -> 429 + Retry-After
  - Reset no virar do mes (dia 1, 00:00 BRT)
  - 1000 consultas OK, 1001a -> 429
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from api_key_rate_limit import (
    API_KEY_TIER_LIMITS,
    _get_brt_now,
    _get_month_key,
    _get_tier_from_plan,
    _seconds_until_next_month,
    check_api_key_rate_limit,
)


# ========================================================================
# Tier mapping tests
# ========================================================================


class TestGetTierFromPlan:
    def test_free_trial_is_starter(self):
        assert _get_tier_from_plan("free_trial") == "starter"

    def test_smartlic_pro_is_pro(self):
        assert _get_tier_from_plan("smartlic_pro") == "pro"

    def test_sala_guerra_is_scale(self):
        assert _get_tier_from_plan("sala_guerra") == "scale"

    def test_master_is_unlimited(self):
        assert _get_tier_from_plan("master") == "unlimited"

    def test_unknown_plan_falls_back_to_starter(self):
        assert _get_tier_from_plan("nonexistent_plan") == "starter"

    def test_consultor_agil_is_starter(self):
        assert _get_tier_from_plan("consultor_agil") == "starter"

    def test_maquina_is_pro(self):
        assert _get_tier_from_plan("maquina") == "pro"

    def test_consultoria_is_scale(self):
        assert _get_tier_from_plan("consultoria") == "scale"

    def test_founding_member_is_scale(self):
        assert _get_tier_from_plan("founding_member") == "scale"

    def test_smartlic_command_is_scale(self):
        assert _get_tier_from_plan("smartlic_command") == "scale"


class TestApiKeyTierLimits:
    def test_starter_1000(self):
        assert API_KEY_TIER_LIMITS["starter"] == 1000

    def test_pro_10000(self):
        assert API_KEY_TIER_LIMITS["pro"] == 10000

    def test_scale_100000(self):
        assert API_KEY_TIER_LIMITS["scale"] == 100000

    def test_unlimited_very_high(self):
        assert API_KEY_TIER_LIMITS["unlimited"] > 1_000_000


# ========================================================================
# Helper tests
# ========================================================================


class TestGetBrtNow:
    def test_returns_datetime(self):
        now = _get_brt_now()
        assert isinstance(now, datetime)
        # Should be within reasonable range from UTC
        utc_now = datetime.now(timezone.utc)
        diff = (utc_now - now).total_seconds()
        # BRT = UTC-3, so diff should be ~3 hours
        assert 2.5 * 3600 < diff < 3.5 * 3600


class TestGetMonthKey:
    def test_returns_yyyy_mm_format(self):
        key = _get_month_key()
        assert len(key) == 7
        parts = key.split("-")
        assert len(parts) == 2
        assert parts[0].isdigit()  # year
        assert parts[1].isdigit()  # month
        assert 1 <= int(parts[1]) <= 12


class TestSecondsUntilNextMonth:
    def test_returns_positive_value(self):
        seconds = _seconds_until_next_month()
        assert seconds >= 1

    def test_returns_reasonable_value(self):
        """Should return at most ~32 days worth of seconds."""
        seconds = _seconds_until_next_month()
        assert seconds <= 32 * 24 * 3600


# ========================================================================
# Main rate limit check tests
# ========================================================================


class TestCheckApiKeyRateLimit:
    """Tests for check_api_key_rate_limit with mocked Redis and plan."""

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_allows_requests_within_limit(
        self, mock_get_plan, mock_redis_pool
    ):
        """Request is allowed when under monthly limit (smartlic_pro -> pro)."""
        mock_get_plan.return_value = "smartlic_pro"
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 50
        mock_redis_pool.return_value = mock_redis

        remaining, limit = await check_api_key_rate_limit(
            api_key_id="key-123",
            user_id="user-abc",
        )

        assert limit == 10000  # smartlic_pro -> pro
        assert remaining == 9950
        mock_redis.incr.assert_called_once()
        mock_redis.expire.assert_not_called()  # count != 1

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_sets_ttl_on_first_request(
        self, mock_get_plan, mock_redis_pool
    ):
        """First request (count == 1) sets TTL until next month."""
        mock_get_plan.return_value = "free_trial"
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1
        mock_redis_pool.return_value = mock_redis

        remaining, limit = await check_api_key_rate_limit(
            api_key_id="key-123",
            user_id="user-abc",
        )

        assert remaining == 999  # Starter limit 1000 - 1
        mock_redis.expire.assert_called_once()
        # TTL should be a positive number of seconds
        ttl_arg = mock_redis.expire.call_args[0][1]
        assert ttl_arg >= 1

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_returns_429_when_exceeded(
        self, mock_get_plan, mock_redis_pool
    ):
        """Request exceeding monthly limit raises 429 with headers."""
        mock_get_plan.return_value = "free_trial"
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 1001  # Over starter limit of 1000
        mock_redis_pool.return_value = mock_redis

        with pytest.raises(HTTPException) as exc_info:
            await check_api_key_rate_limit(
                api_key_id="key-123",
                user_id="user-abc",
            )

        assert exc_info.value.status_code == 429
        headers = exc_info.value.headers
        assert headers is not None
        assert headers["X-RateLimit-Limit"] == "1000"
        assert headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in headers
        retry_after = int(headers["Retry-After"])
        assert retry_after >= 1

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_exact_limit_boundary_starter(
        self, mock_get_plan, mock_redis_pool
    ):
        """AC: 1,000th request OK, 1,001st -> 429 for Starter tier."""
        mock_get_plan.return_value = "free_trial"  # -> starter -> 1000 limit
        mock_redis = AsyncMock()
        mock_redis_pool.return_value = mock_redis

        # Exactly at limit (1000) - should be allowed
        mock_redis.incr.return_value = 1000
        remaining, limit = await check_api_key_rate_limit(
            api_key_id="key-123",
            user_id="user-abc",
        )
        assert remaining == 0
        assert limit == 1000

        # One over (1001) - should raise 429
        mock_redis.incr.return_value = 1001
        with pytest.raises(HTTPException) as exc_info:
            await check_api_key_rate_limit(
                api_key_id="key-123",
                user_id="user-abc",
            )
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_different_tiers_have_different_limits(
        self, mock_get_plan, mock_redis_pool
    ):
        """Each tier has its own limit (starter < pro < scale)."""
        mock_redis = AsyncMock()
        mock_redis_pool.return_value = mock_redis

        # Starter: 1000 limit
        mock_get_plan.return_value = "free_trial"
        mock_redis.incr.return_value = 500
        remaining_starter, limit_starter = await check_api_key_rate_limit(
            api_key_id="key-123",
            user_id="user-abc",
        )
        assert limit_starter == 1000

        # Pro: 10000 limit
        mock_get_plan.return_value = "smartlic_pro"
        mock_redis.incr.return_value = 500
        remaining_pro, limit_pro = await check_api_key_rate_limit(
            api_key_id="key-456",
            user_id="user-def",
        )
        assert limit_pro == 10000

        # Scale: 100000 limit
        mock_get_plan.return_value = "sala_guerra"
        mock_redis.incr.return_value = 500
        remaining_scale, limit_scale = await check_api_key_rate_limit(
            api_key_id="key-789",
            user_id="user-ghi",
        )
        assert limit_scale == 100000

        # Unlimited: very high limit
        mock_get_plan.return_value = "master"
        mock_redis.incr.return_value = 500
        remaining_master, limit_master = await check_api_key_rate_limit(
            api_key_id="key-master",
            user_id="user-master",
        )
        assert limit_master > 1_000_000

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_fail_open_when_redis_unavailable(
        self, mock_get_plan, mock_redis_pool
    ):
        """When Redis is None, allow request (fail-open)."""
        mock_get_plan.return_value = "smartlic_pro"
        mock_redis_pool.return_value = None

        remaining, limit = await check_api_key_rate_limit(
            api_key_id="key-123",
            user_id="user-abc",
        )

        # Fail-open: returns (limit, limit) so remaining == limit
        assert limit == 10000
        assert remaining == 10000

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_fail_open_on_redis_error(
        self, mock_get_plan, mock_redis_pool
    ):
        """When Redis raises an error, allow request (fail-open)."""
        mock_get_plan.return_value = "free_trial"
        mock_redis = AsyncMock()
        mock_redis.incr.side_effect = Exception("Redis connection lost")
        mock_redis_pool.return_value = mock_redis

        remaining, limit = await check_api_key_rate_limit(
            api_key_id="key-123",
            user_id="user-abc",
        )

        # Fail-open: returns (limit, limit)
        assert limit == 1000
        assert remaining == 1000

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_pro_limit_not_reached(
        self, mock_get_plan, mock_redis_pool
    ):
        """Pro tier allows up to 10000 requests."""
        mock_get_plan.return_value = "smartlic_pro"
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 9999  # Just under limit
        mock_redis_pool.return_value = mock_redis

        remaining, limit = await check_api_key_rate_limit(
            api_key_id="key-pro",
            user_id="user-pro",
        )

        assert remaining == 1  # 10000 - 9999
        assert limit == 10000

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_pro_limit_exceeded(
        self, mock_get_plan, mock_redis_pool
    ):
        """Pro tier returns 429 when limit exceeded."""
        mock_get_plan.return_value = "smartlic_pro"
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 10001  # Over pro limit
        mock_redis_pool.return_value = mock_redis

        with pytest.raises(HTTPException) as exc_info:
            await check_api_key_rate_limit(
                api_key_id="key-pro",
                user_id="user-pro",
            )
        assert exc_info.value.status_code == 429
        assert exc_info.value.headers["X-RateLimit-Limit"] == "10000"

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_scale_limit_allows_high_usage(
        self, mock_get_plan, mock_redis_pool
    ):
        """Scale tier allows 100000 requests."""
        mock_get_plan.return_value = "sala_guerra"
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 50000  # Half of scale
        mock_redis_pool.return_value = mock_redis

        remaining, limit = await check_api_key_rate_limit(
            api_key_id="key-scale",
            user_id="user-scale",
        )

        assert remaining == 50000
        assert limit == 100000

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_scale_limit_exceeded(
        self, mock_get_plan, mock_redis_pool
    ):
        """Scale tier returns 429 when limit exceeded."""
        mock_get_plan.return_value = "sala_guerra"
        mock_redis = AsyncMock()
        mock_redis.incr.return_value = 100001  # Over scale limit
        mock_redis_pool.return_value = mock_redis

        with pytest.raises(HTTPException) as exc_info:
            await check_api_key_rate_limit(
                api_key_id="key-scale",
                user_id="user-scale",
            )
        assert exc_info.value.status_code == 429
        assert exc_info.value.headers["X-RateLimit-Limit"] == "100000"

    @pytest.mark.asyncio
    @patch("api_key_rate_limit.get_redis_pool", new_callable=AsyncMock)
    @patch("api_key_rate_limit._get_user_plan")
    async def test_unlimited_master_never_429(
        self, mock_get_plan, mock_redis_pool
    ):
        """Master tier has unlimited requests - never 429."""
        mock_get_plan.return_value = "master"
        mock_redis = AsyncMock()
        # Even a very high count should not trigger 429 for master
        mock_redis.incr.return_value = 500_000
        mock_redis_pool.return_value = mock_redis

        remaining, limit = await check_api_key_rate_limit(
            api_key_id="key-master",
            user_id="user-master",
        )

        assert limit > 1_000_000
        assert remaining > 0
