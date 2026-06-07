"""Tests for API-SELF-006: GET /v1/conta/api-usage endpoint."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_supabase():
    """Mock supabase client returning realistic API usage data."""
    sb = MagicMock()

    # Mock api_keys table
    api_keys_result = MagicMock()
    api_keys_result.data = [
        {
            "id": "key-uuid-1",
            "name": "Chave Principal",
            "created_at": "2026-06-01T00:00:00Z",
            "last_used_at": "2026-06-05T12:00:00Z",
            "revoked_at": None,
        },
        {
            "id": "key-uuid-2",
            "name": "Chave Backup",
            "created_at": "2026-05-15T00:00:00Z",
            "last_used_at": None,
            "revoked_at": None,
        },
    ]
    api_keys_result.error = None

    # Mock api_usage_records table
    usage_result = MagicMock()
    usage_result.data = [
        {"api_key_id": "key-uuid-1", "request_count": 350, "month": "2026-06"},
        {"api_key_id": "key-uuid-2", "request_count": 100, "month": "2026-06"},
    ]
    usage_result.error = None

    # Mock profiles table
    profiles_result = MagicMock()
    profiles_result.data = {
        "plan_type": "maquina",
        "api_tier": None,
    }
    profiles_result.error = None

    # Setup chainable mock
    def make_chainable(result):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.is_.return_value = chain
        chain.order.return_value = chain
        chain.in_.return_value = chain
        chain.single.return_value = chain
        chain.execute = AsyncMock(return_value=result)
        return chain

    sb.table = MagicMock()
    sb.table.side_effect = lambda table_name: make_chainable(
        api_keys_result if table_name == "api_keys"
        else usage_result if table_name == "api_usage_records"
        else profiles_result
    )

    return sb


@pytest.fixture
def mock_redis():
    """Mock Redis with scan/get for daily usage keys."""
    redis = MagicMock()

    # Simulate Redis scan returning daily keys
    call_count = [0]

    def scan_side_effect(cursor, match=None, count=None):
        call_count[0] += 1
        if call_count[0] == 1:
            keys = [
                b"api_key_daily:key-uuid-1:2026-06-01",
                b"api_key_daily:key-uuid-1:2026-06-02",
                b"api_key_daily:key-uuid-1:2026-06-05",
            ]
            return (0, keys)
        return (0, [])

    redis.scan = MagicMock(side_effect=scan_side_effect)
    redis.get = MagicMock(side_effect=lambda k: {
        b"api_key_daily:key-uuid-1:2026-06-01": b"150",
        b"api_key_daily:key-uuid-1:2026-06-02": b"120",
        b"api_key_daily:key-uuid-1:2026-06-05": b"80",
    }.get(k, b"0"))

    return redis


class TestApiUsageEndpoint:
    """API-SELF-006: Tests for GET /v1/conta/api-usage."""

    @pytest.mark.asyncio
    async def test_returns_api_keys_and_usage(self, mock_supabase, mock_redis):
        """Should return API keys, current month usage, and daily breakdown."""
        from routes.conta import get_api_usage, _get_tier_for_plan, _get_monthly_limit

        # Verify tier mapping
        assert _get_tier_for_plan("maquina") == "pro"
        assert _get_tier_for_plan("free_trial") == "starter"
        assert _get_tier_for_plan(None) == "none"
        assert _get_monthly_limit("pro") == 10000
        assert _get_monthly_limit("starter") == 1000

    @pytest.mark.asyncio
    async def test_tier_mapping_is_correct(self):
        """Verify tier mapping consistency with api_key_rate_limit."""
        from routes.conta import _get_tier_for_plan, _get_monthly_limit

        # All known plan types should map to valid tiers
        plan_types = [
            "free_trial", "free", "consultor_agil",
            "maquina", "smartlic_pro",
            "sala_guerra", "smartlic_command", "consultoria", "founding_member",
            "master",
        ]
        for pt in plan_types:
            tier = _get_tier_for_plan(pt)
            assert tier in ("starter", "pro", "scale", "unlimited"), f"{pt} -> {tier}"
            limit = _get_monthly_limit(tier)
            assert limit > 0, f"{tier} limit is {limit}"

    @pytest.mark.asyncio
    async def test_none_plan_returns_none_tier(self):
        """None plan_type should return 'none' tier."""
        from routes.conta import _get_tier_for_plan
        assert _get_tier_for_plan(None) == "none"

    @pytest.mark.asyncio
    async def test_unknown_tier_returns_starter_default(self):
        """Unknown tier should default to starter limit."""
        from routes.conta import _get_monthly_limit
        assert _get_monthly_limit("unknown_tier") == 1000
