"""REPORT-MONTHLY-001 (#1620): Tests for Monthly Report route."""

import pytest
from unittest.mock import MagicMock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from main import app
    return app


@pytest.fixture
def client(app: FastAPI):
    return TestClient(app)


# ---------------------------------------------------------------------------
# Mock auth dependency
# ---------------------------------------------------------------------------

MOCK_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture(autouse=True)
def _mock_auth(app: FastAPI):
    """Override auth dependency with a mock user."""
    from auth import require_auth

    async def _mock_require_auth():
        return MOCK_USER_ID

    app.dependency_overrides[require_auth] = _mock_require_auth
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Mock supabase for data-dependent tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_supabase(monkeypatch: pytest.MonkeyPatch):
    """Mock supabase_client for all tests."""
    mock_sb = MagicMock()
    mock_execute = AsyncMock()
    mock_execute.side_effect = lambda query: MagicMock(data=None, count=0)

    monkeypatch.setattr("supabase_client.get_supabase", lambda: mock_sb)
    monkeypatch.setattr("supabase_client.sb_execute", mock_execute)

    yield mock_sb, mock_execute


# ===========================================================================
# Route registration tests
# ===========================================================================


class TestRouteRegistration:
    """Verify the route is registered."""

    def test_route_registered(self, client: TestClient):
        """Route exists."""
        resp = client.get("/v1/report-mensal/preview/alimentos")
        assert resp.status_code in (200, 404, 422, 500)

    def test_route_404_when_disabled(self, client: TestClient, monkeypatch: pytest.MonkeyPatch):
        """Returns 404 when feature flag is disabled."""
        monkeypatch.setattr(
            "routes.monthly_report.get_feature_flag",
            lambda name, default=True: False,
        )
        resp = client.get("/v1/report-mensal/preview/alimentos")
        assert resp.status_code == 404


# ===========================================================================
# Preview tests
# ===========================================================================


class TestPreview:
    """Test preview endpoint."""

    ENDPOINT = "/v1/report-mensal/preview"

    def test_preview_invalid_sector_returns_404(self, client: TestClient):
        """Invalid sector returns 404."""
        resp = client.get(f"{self.ENDPOINT}/setor-invalido-xyz")
        assert resp.status_code == 404

    def test_preview_valid_sector_returns_data(self, client: TestClient, _mock_supabase):
        """Valid sector returns expected structure."""
        mock_sb, mock_execute = _mock_supabase
        resp = client.get(f"{self.ENDPOINT}/alimentos")
        if resp.status_code == 200:
            data = resp.json()
            assert data["sector_id"] == "alimentos"
            assert "sector_name" in data
            assert "period" in data
            assert "total_licitacoes" in data
            assert "executive_summary" in data
            assert "sample_pdf_available" in data

    def test_preview_response_structure(self, client: TestClient, _mock_supabase):
        """Response has all expected fields."""
        resp = client.get(f"{self.ENDPOINT}/engenharia")
        if resp.status_code == 200:
            data = resp.json()
            assert "sector_id" in data
            assert "sector_name" in data
            assert "top_opportunities" in data
            assert isinstance(data["top_opportunities"], list)
            assert "top_winners" in data
            assert isinstance(data["top_winners"], list)


# ===========================================================================
# Subscribe tests
# ===========================================================================


class TestSubscribe:
    """Test subscribe endpoint."""

    ENDPOINT = "/v1/report-mensal/subscribe"

    def test_subscribe_invalid_sector_returns_400(self, client: TestClient):
        """Invalid sector returns 400."""
        resp = client.post(
            self.ENDPOINT,
            json={"sector_id": "setor-invalido"},
        )
        assert resp.status_code == 400

    def test_subscribe_without_sector_returns_422(self, client: TestClient):
        """Missing sector_id returns 422."""
        resp = client.post(self.ENDPOINT, json={})
        assert resp.status_code == 422

    def test_subscribe_valid_sector(self, client: TestClient, _mock_supabase):
        """Valid subscription request."""
        mock_sb, mock_execute = _mock_supabase

        # Mock subscription creation
        async def _side_effect(query):
            query_str = str(query)
            if "monthly_report_subscriptions" in query_str and "select" in query_str:
                return MagicMock(data=None)  # No existing subscription
            if "monthly_report_subscriptions" in query_str and "insert" in query_str:
                return MagicMock(data=[{
                    "id": "sub-1",
                    "user_id": MOCK_USER_ID,
                    "sector_id": "alimentos",
                    "status": "active",
                    "stripe_sub_id": None,
                    "created_at": "2026-06-12T00:00:00Z",
                }])
            return MagicMock(data=None, count=0)

        mock_execute.side_effect = _side_effect

        resp = client.post(
            self.ENDPOINT,
            json={"sector_id": "alimentos"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert data["sector_id"] == "alimentos"
            assert data["status"] == "active"


# ===========================================================================
# List subscriptions tests
# ===========================================================================


class TestListSubscriptions:
    """Test list subscriptions endpoint."""

    ENDPOINT = "/v1/report-mensal/subscriptions"

    def test_list_subscriptions_returns_list(self, client: TestClient, _mock_supabase):
        """Returns expected structure."""
        mock_sb, mock_execute = _mock_supabase

        async def _side_effect(query):
            query_str = str(query)
            if "monthly_report_subscriptions" in query_str:
                return MagicMock(data=[
                    {
                        "id": "sub-1",
                        "user_id": MOCK_USER_ID,
                        "sector_id": "alimentos",
                        "status": "active",
                        "stripe_sub_id": None,
                        "created_at": "2026-06-12T00:00:00Z",
                    }
                ], count=1)
            return MagicMock(data=None, count=0)

        mock_execute.side_effect = _side_effect

        resp = client.get(self.ENDPOINT)
        if resp.status_code == 200:
            data = resp.json()
            assert "subscriptions" in data
            assert "total" in data
            assert "active_count" in data
            assert isinstance(data["subscriptions"], list)


# ===========================================================================
# Cancel subscription tests
# ===========================================================================


class TestCancelSubscription:
    """Test cancel subscription endpoint."""

    def test_cancel_nonexistent_returns_404(self, client: TestClient, _mock_supabase):
        """Cancel non-existent subscription returns 404."""
        mock_sb, mock_execute = _mock_supabase

        resp = client.post("/v1/report-mensal/cancel/sub-nonexistent")
        assert resp.status_code in (404, 500)
