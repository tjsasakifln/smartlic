"""Tests for NETINT-014 (#1519): pseo_intel_feed endpoint.

Tests:
- Returns 200 with valid sector
- Returns 404 for missing sector
- Response structure matches IntelFeedResponse schema
- Handles cache correctly
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear intel feed cache between tests."""
    from routes.pseo_intel_feed import _feed_cache
    _feed_cache.clear()
    yield
    _feed_cache.clear()


@pytest.fixture
def client():
    from main import app
    return TestClient(app)


class TestPseoIntelFeed:
    """Test suite for GET /v1/pseo/intel-feed."""

    VALID_SECTOR = "engenharia"
    INVALID_SECTOR = "setor-inexistente"

    def test_returns_200_with_valid_sector(self, client):
        """Should return 200 with valid sector."""
        resp = client.get(f"/v1/pseo/intel-feed?sector={self.VALID_SECTOR}")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    def test_returns_404_for_invalid_sector(self, client):
        """Should return 404 for non-existent sector."""
        resp = client.get(f"/v1/pseo/intel-feed?sector={self.INVALID_SECTOR}")
        assert resp.status_code == 404

    def test_returns_422_when_sector_missing(self, client):
        """Should return 422 when sector param is omitted (FastAPI validation)."""
        resp = client.get("/v1/pseo/intel-feed")
        assert resp.status_code == 422

    def test_response_structure_matches_schema(self, client):
        """Response should match IntelFeedResponse schema."""
        resp = client.get(f"/v1/pseo/intel-feed?sector={self.VALID_SECTOR}" +
                          "&uf=SP")
        assert resp.status_code == 200
        data = resp.json()

        # Check top-level fields
        assert "sector" in data
        assert "signals" in data
        assert "generated_at" in data

        # sector should be a non-empty string
        assert isinstance(data["sector"], str) and len(data["sector"]) > 0

        # signals should be a list with 3 items
        assert isinstance(data["signals"], list)
        assert len(data["signals"]) == 3

        # Each signal should have label and value
        for signal in data["signals"]:
            assert "label" in signal
            assert "value" in signal
            assert isinstance(signal["label"], str)
            assert isinstance(signal["value"], str)

        # generated_at should be a valid ISO datetime
        assert isinstance(data["generated_at"], str)
        from datetime import datetime
        datetime.fromisoformat(data["generated_at"])

    def test_cache_hit(self, client):
        """Second request should return from cache (fast)."""
        # First request populates cache
        resp1 = client.get(f"/v1/pseo/intel-feed?sector={self.VALID_SECTOR}")
        assert resp1.status_code == 200

        # Second request should be fast (from cache)
        resp2 = client.get(f"/v1/pseo/intel-feed?sector={self.VALID_SECTOR}")
        assert resp2.status_code == 200
        assert resp2.json()["sector"] == resp1.json()["sector"]

    def test_different_sectors_return_different_data(self, client):
        """Different sectors should return different responses."""
        resp_eng = client.get("/v1/pseo/intel-feed?sector=engenharia")
        resp_vest = client.get("/v1/pseo/intel-feed?sector=vestuario")
        assert resp_eng.status_code == 200
        assert resp_vest.status_code == 200
        # At minimum the sector name should differ
        assert resp_eng.json()["sector"] != resp_vest.json()["sector"]
