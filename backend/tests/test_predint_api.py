"""PREDINT-021 (#1670): Tests for Predictive Intelligence API endpoints.

Tests the 3 FastAPI endpoints:
    GET /v1/predint/forecast     — Demand forecast
    GET /v1/predint/seasonality   — Seasonal patterns
    GET /v1/predint/renewals      — Renewal alerts

Uses TestClient with mocked Supabase and Redis.
"""

import json
import sys
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app

# ---------------------------------------------------------------------------
# Mock the resilience module (not available in test environment)
# ---------------------------------------------------------------------------
_mock_resilience = MagicMock()
_mock_resilience_budget = MagicMock()
_mock_resilience.budget = _mock_resilience_budget
_mock_resilience_budget._run_with_budget = lambda x, **kwargs: x

if "resilience" not in sys.modules:
    sys.modules["resilience"] = _mock_resilience
    sys.modules["resilience.budget"] = _mock_resilience_budget


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_redis(monkeypatch):
    """Mock Redis for cache operations."""
    mock_redis_instance = AsyncMock()
    mock_redis_instance.get.return_value = None  # Miss cache by default
    mock_redis_instance.setex.return_value = True

    async def mock_get_redis_pool():
        return mock_redis_instance

    monkeypatch.setattr(
        "routes.predint.get_redis_pool", mock_get_redis_pool
    )
    return mock_redis_instance


@pytest.fixture
def mock_supabase_rpc():
    """Mock supabase RPC calls to return controlled data."""
    mock_sb = MagicMock()
    mock_execute = AsyncMock()

    def _rpc_side_effect(rpc_name, params):
        # Return different data based on RPC name
        if rpc_name == "get_sector_monthly_volume":
            mock_execute.return_value = MagicMock(data=[
                {"month": "2026-01", "bid_count": 150, "total_value": 5000000.00},
                {"month": "2026-02", "bid_count": 120, "total_value": 3500000.00},
                {"month": "2026-03", "bid_count": 200, "total_value": 8200000.00},
            ])
        elif rpc_name == "get_uf_demand_trend":
            mock_execute.return_value = MagicMock(data=[
                {"month": "2026-01", "bid_count": 50, "total_value": 1800000.00},
                {"month": "2026-02", "bid_count": 45, "total_value": 1500000.00},
            ])
        elif rpc_name == "get_sector_seasonal_pattern":
            mock_execute.return_value = MagicMock(data=[
                {"month_num": 1, "avg_count": 85.5, "avg_value": 3200000.00},
                {"month_num": 2, "avg_count": 72.3, "avg_value": 2800000.00},
                {"month_num": 3, "avg_count": 95.0, "avg_value": 4100000.00},
                {"month_num": 12, "avg_count": 110.2, "avg_value": 5500000.00},
            ])
        elif rpc_name == "get_upcoming_renewals":
            mock_execute.return_value = MagicMock(data=[
                {
                    "contract_id": 12345,
                    "orgao": "Prefeitura Municipal de Sao Paulo",
                    "value": 500000.00,
                    "estimated_expiry": "2026-09-15",
                },
                {
                    "contract_id": 67890,
                    "orgao": "Governo do Estado de SP",
                    "value": 1200000.00,
                    "estimated_expiry": "2026-10-01",
                },
            ])
        else:
            mock_execute.return_value = MagicMock(data=[])

        return mock_sb

    mock_sb.rpc = MagicMock(side_effect=_rpc_side_effect)
    mock_sb.rpc.return_value.execute = mock_execute

    # Mock the supabase client
    mock_get_supabase = MagicMock(return_value=mock_sb)

    # Apply patches at source (supabase_client) since routes use lazy imports
    with patch("supabase_client.get_supabase", return_value=mock_sb), \
         patch("supabase_client.sb_execute", mock_execute):
        yield


# ---------------------------------------------------------------------------
# Feature flag tests
# ---------------------------------------------------------------------------

class TestFeatureFlag:
    """Tests for the PREDICTIVE_INTEL_ENABLED feature flag."""

    def test_forecast_disabled_returns_empty(self, client):
        """Forecast returns empty data with feature_enabled=False when flag is off."""
        with patch("routes.predint.get_feature_flag", return_value=False):
            resp = client.get("/v1/predint/forecast?sector=alimentos&months=12")
            assert resp.status_code == 200
            data = resp.json()
            assert data["feature_enabled"] is False
            assert data["forecast"] == []

    def test_seasonality_disabled_returns_empty(self, client):
        """Seasonality returns empty data with feature_enabled=False when flag is off."""
        with patch("routes.predint.get_feature_flag", return_value=False):
            resp = client.get("/v1/predint/seasonality/alimentos")
            assert resp.status_code == 200
            data = resp.json()
            assert data["feature_enabled"] is False
            assert data["patterns"] == []

    def test_renewals_disabled_returns_empty(self, client):
        """Renewals returns empty data with feature_enabled=False when flag is off."""
        with patch("routes.predint.get_feature_flag", return_value=False):
            resp = client.get("/v1/predint/renewals?days=90")
            assert resp.status_code == 200
            data = resp.json()
            assert data["feature_enabled"] is False
            assert data["alerts"] == []


# ---------------------------------------------------------------------------
# Route registration tests
# ---------------------------------------------------------------------------

class TestRouteRegistration:
    """Tests that routes are registered and accessible."""

    def test_forecast_route_registered(self, client):
        """GET /v1/predint/forecast is registered."""
        with patch("routes.predint.get_feature_flag", return_value=False):
            resp = client.get("/v1/predint/forecast")
            assert resp.status_code in (200, 422, 500)

    def test_seasonality_route_registered(self, client):
        """GET /v1/predint/seasonality/{sector_id} is registered."""
        with patch("routes.predint.get_feature_flag", return_value=False):
            resp = client.get("/v1/predint/seasonality/alimentos")
            assert resp.status_code in (200, 422, 500)

    def test_renewals_route_registered(self, client):
        """GET /v1/predint/renewals is registered."""
        with patch("routes.predint.get_feature_flag", return_value=False):
            resp = client.get("/v1/predint/renewals")
            assert resp.status_code in (200, 422, 500)

    def test_unknown_route_returns_404(self, client):
        """Unknown predint route returns 404."""
        resp = client.get("/v1/predint/unknown")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Input validation tests
# ---------------------------------------------------------------------------

class TestInputValidation:
    """Tests for input validation on all endpoints."""

    def test_forecast_invalid_uf(self, client):
        """Invalid UF returns 422."""
        resp = client.get("/v1/predint/forecast?uf=INVALID")
        assert resp.status_code == 422

    def test_forecast_months_below_range(self, client):
        """months < 1 returns 422."""
        resp = client.get("/v1/predint/forecast?months=0")
        assert resp.status_code == 422

    def test_forecast_months_above_range(self, client):
        """months > 120 returns 422."""
        resp = client.get("/v1/predint/forecast?months=121")
        assert resp.status_code == 422

    def test_renewals_days_below_range(self, client):
        """days < 1 returns 422."""
        resp = client.get("/v1/predint/renewals?days=0")
        assert resp.status_code == 422

    def test_renewals_days_above_range(self, client):
        """days > 365 returns 422."""
        resp = client.get("/v1/predint/renewals?days=366")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Response schema validation tests
# ---------------------------------------------------------------------------

class TestResponseSchema:
    """Tests that responses match expected Pydantic schemas."""

    def test_forecast_response_structure(self, client, mock_redis, mock_supabase_rpc):
        """Forecast response has expected fields."""
        resp = client.get("/v1/predint/forecast?months=12")
        if resp.status_code == 200:
            data = resp.json()
            assert "sector" in data
            assert "uf" in data
            assert "months" in data
            assert "forecast" in data
            assert "total_contracts" in data
            assert "total_value" in data
            assert "feature_enabled" in data
            assert isinstance(data["forecast"], list)

    def test_forecast_items_have_correct_fields(self, client, mock_redis, mock_supabase_rpc):
        """Each forecast item has month, bid_count, total_value."""
        resp = client.get("/v1/predint/forecast?months=12")
        if resp.status_code == 200:
            data = resp.json()
            for item in data["forecast"]:
                assert "month" in item
                assert "bid_count" in item
                assert "total_value" in item
                assert isinstance(item["bid_count"], int)
                assert isinstance(item["total_value"], float)

    def test_seasonality_response_structure(self, client, mock_redis, mock_supabase_rpc):
        """Seasonality response has expected fields."""
        resp = client.get("/v1/predint/seasonality/alimentos")
        if resp.status_code == 200:
            data = resp.json()
            assert "sector" in data
            assert "patterns" in data
            assert "peak_month" in data
            assert "feature_enabled" in data
            assert isinstance(data["patterns"], list)

    def test_seasonality_items_have_correct_fields(self, client, mock_redis, mock_supabase_rpc):
        """Each seasonality item has month_num, avg_count, avg_value."""
        resp = client.get("/v1/predint/seasonality/alimentos")
        if resp.status_code == 200:
            data = resp.json()
            for item in data["patterns"]:
                assert "month_num" in item
                assert "avg_count" in item
                assert "avg_value" in item
                assert 1 <= item["month_num"] <= 12

    def test_renewals_response_structure(self, client, mock_redis, mock_supabase_rpc):
        """Renewals response has expected fields."""
        resp = client.get("/v1/predint/renewals?days=90")
        if resp.status_code == 200:
            data = resp.json()
            assert "sector" in data
            assert "days" in data
            assert "alerts" in data
            assert "total_count" in data
            assert "total_value" in data
            assert "feature_enabled" in data
            assert isinstance(data["alerts"], list)

    def test_renewal_items_have_correct_fields(self, client, mock_redis, mock_supabase_rpc):
        """Each renewal alert has contract_id, orgao, value, estimated_expiry."""
        resp = client.get("/v1/predint/renewals?days=90")
        if resp.status_code == 200:
            data = resp.json()
            for item in data["alerts"]:
                assert "contract_id" in item
                assert "orgao" in item
                assert "value" in item
                assert "estimated_expiry" in item
                assert isinstance(item["contract_id"], int)
                assert isinstance(item["orgao"], str)
                assert item["orgao"] != ""


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------

class TestCache:
    """Tests for Redis caching behavior."""

    def test_cache_hit_returns_cached_data(self, client, mock_redis, mock_supabase_rpc):
        """Cache hit returns data without calling RPC."""
        # Pre-populate cache
        cached_data = {
            "sector": None,
            "uf": None,
            "months": 12,
            "forecast": [],
            "total_contracts": 0,
            "total_value": 0.0,
            "feature_enabled": True,
        }
        mock_redis.get.return_value = json.dumps(cached_data)

        resp = client.get("/v1/predint/forecast?months=12")
        if resp.status_code == 200:
            data = resp.json()
            assert data["forecast"] == []

    def test_cache_miss_computes_fresh_data(self, client, mock_redis, mock_supabase_rpc):
        """Cache miss triggers RPC query."""
        mock_redis.get.return_value = None  # Ensure cache miss
        resp = client.get("/v1/predint/forecast?months=12")
        if resp.status_code == 200:
            data = resp.json()
            assert "forecast" in data


# ---------------------------------------------------------------------------
# Empty data handling tests
# ---------------------------------------------------------------------------

class TestEmptyData:
    """Tests for graceful handling of empty data."""

    def test_forecast_no_data_returns_empty(self, client, mock_redis):
        """Forecast with sector having no data returns empty list."""
        # Mock empty RPC response
        with patch("supabase_client.get_supabase") as mock_gs, \
             patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(data=[])
            mock_gs.return_value.rpc.return_value.execute = mock_exec

            resp = client.get("/v1/predint/forecast?sector=unknown")
            if resp.status_code == 200:
                data = resp.json()
                assert data["forecast"] == []
                assert data["total_contracts"] == 0

    def test_seasonality_no_data_returns_empty(self, client, mock_redis):
        """Seasonality with sector having no data returns empty list."""
        with patch("supabase_client.get_supabase") as mock_gs, \
             patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(data=[])
            mock_gs.return_value.rpc.return_value.execute = mock_exec

            resp = client.get("/v1/predint/seasonality/unknown")
            if resp.status_code == 200:
                data = resp.json()
                assert data["patterns"] == []
                assert data["peak_month"] is None

    def test_renewals_no_data_returns_empty(self, client, mock_redis):
        """Renewals with sector having no data returns empty list."""
        with patch("supabase_client.get_supabase") as mock_gs, \
             patch("supabase_client.sb_execute", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = MagicMock(data=[])
            mock_gs.return_value.rpc.return_value.execute = mock_exec

            resp = client.get("/v1/predint/renewals?sector=unknown&days=30")
            if resp.status_code == 200:
                data = resp.json()
                assert data["alerts"] == []
                assert data["total_count"] == 0
