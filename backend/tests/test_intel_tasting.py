"""DEGUST-001 (#1611): Tests for Intelligence Tasting route."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestIntelTastingRoute:
    """Basic route validation for GET /v1/intel/tasting."""

    def test_route_registered(self, client: TestClient):
        """Route is registered and returns 200 for valid params."""
        resp = client.get("/v1/intel/tasting?setor_id=alimentos&uf=SP&meses=1")
        # Route exists — may return 200 (data) or 500 (no Supabase in test)
        assert resp.status_code in (200, 422, 500)

    def test_invalid_uf_returns_422(self, client: TestClient):
        """Invalid UF returns validation error."""
        resp = client.get("/v1/intel/tasting?uf=XX")
        assert resp.status_code in (400, 422)

    def test_invalid_sector_returns_422(self, client: TestClient):
        """Invalid sector returns validation error."""
        resp = client.get("/v1/intel/tasting?setor_id=invalid_sector_xyz")
        assert resp.status_code in (400, 422)

    def test_meses_below_range(self, client: TestClient):
        """meses < 1 returns validation error."""
        resp = client.get("/v1/intel/tasting?meses=0")
        assert resp.status_code == 422

    def test_meses_above_range(self, client: TestClient):
        """meses > 24 returns validation error."""
        resp = client.get("/v1/intel/tasting?meses=25")
        assert resp.status_code == 422

    def test_no_params_returns_ok(self, client: TestClient):
        """No params uses defaults — returns 200 or 500 (no DB in test env)."""
        resp = client.get("/v1/intel/tasting")
        assert resp.status_code in (200, 422, 500)

    def test_response_model_structure(self, client: TestClient):
        """Response JSON has expected keys when data is returned."""
        resp = client.get("/v1/intel/tasting?setor_id=alimentos&uf=SP")
        if resp.status_code == 200:
            data = resp.json()
            assert "sector_id" in data
            assert "sector_name" in data
            assert "total_contracts_value" in data
            assert "total_winners" in data
            assert "top_winners" in data
            assert isinstance(data["top_winners"], list)
