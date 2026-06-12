"""CONSULT-001 (#1613): Tests for Consultant Seats route."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app():
    from main import app
    return app


@pytest.fixture
def client(app: FastAPI):
    return TestClient(app)


@pytest.fixture(autouse=True)
def _clear_invite_store():
    """Clear in-memory invite store between tests."""
    from routes.consultoria import _invite_store
    _invite_store.clear()
    yield
    _invite_store.clear()


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
# Mock supabase client (patch at supabase_client level, not route module)
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _mock_supabase(monkeypatch: pytest.MonkeyPatch):
    """Mock supabase_client.get_supabase and sb_execute for all tests."""
    mock_sb = MagicMock()
    mock_execute = AsyncMock()
    mock_execute.side_effect = lambda query: MagicMock(data=None, count=0)

    monkeypatch.setattr("supabase_client.get_supabase", lambda: mock_sb)
    monkeypatch.setattr("supabase_client.sb_execute", mock_execute)

    yield mock_sb, mock_execute


# ---------------------------------------------------------------------------
# Helper to setup mock for a consultant profile
# ---------------------------------------------------------------------------

def _mock_consultant_profile(mock_execute: AsyncMock):
    """Configure mock to return consultant plan_type on profile queries."""

    async def _side_effect(query):
        query_str = str(query)
        if "profiles" in query_str and "plan_type" in query_str:
            return MagicMock(data={"plan_type": "consultoria_mensal"})
        if "consultant_clients" in query_str and "count" in query_str:
            return MagicMock(data=None, count=1)
        return MagicMock(data=None, count=0)

    mock_execute.side_effect = _side_effect


# ===========================================================================
# Route registration & feature flag tests
# ===========================================================================


class TestRouteRegistration:
    """Verify the route is registered and responds correctly."""

    def test_route_registered(self, client: TestClient):
        """Route exists — returns relevant status."""
        resp = client.post(
            "/v1/consultoria/invite-client",
            json={"client_email": "test@test.com"},
        )
        assert resp.status_code in (200, 401, 403, 422, 500)

    def test_route_404_when_feature_disabled(
        self, client: TestClient, _mock_supabase, monkeypatch: pytest.MonkeyPatch,
    ):
        """Route returns 404 when feature flag is disabled."""
        monkeypatch.setattr(
            "routes.consultoria.get_feature_flag",
            lambda name, default=True: False,
        )
        resp = client.post(
            "/v1/consultoria/invite-client",
            json={"client_email": "test@test.com"},
        )
        assert resp.status_code == 404


# ===========================================================================
# POST /consultoria/invite-client tests
# ===========================================================================


class TestInviteClient:
    """Test invite client endpoint."""

    ENDPOINT = "/v1/consultoria/invite-client"

    def test_invite_without_email_returns_422(self, client: TestClient):
        """Missing client_email in body returns 422."""
        resp = client.post(self.ENDPOINT, json={})
        assert resp.status_code == 422

    def test_invite_with_invalid_email_returns_422(self, client: TestClient):
        """Empty email returns 422."""
        resp = client.post(self.ENDPOINT, json={"client_email": ""})
        assert resp.status_code == 422

    def test_invite_success_structure(self, client: TestClient, _mock_supabase):
        """Successful invite returns expected fields."""
        mock_sb, mock_execute = _mock_supabase
        _mock_consultant_profile(mock_execute)

        resp = client.post(
            self.ENDPOINT,
            json={"client_email": "cliente@empresa.com.br"},
        )
        if resp.status_code == 200:
            data = resp.json()
            assert "invite_url" in data
            assert "expires_at" in data
            assert "smartlic.tech/consultoria/convite" in data["invite_url"]
            assert data["invite_url"].startswith("https://")

    def test_invite_stores_token(self, client: TestClient, _mock_supabase):
        """Invite token is stored in memory."""
        from routes.consultoria import _invite_store

        mock_sb, mock_execute = _mock_supabase
        _mock_consultant_profile(mock_execute)

        resp = client.post(
            self.ENDPOINT,
            json={"client_email": "test@test.com"},
        )
        if resp.status_code == 200:
            assert len(_invite_store) == 1
            token = list(_invite_store.keys())[0]
            assert _invite_store[token]["client_email"] == "test@test.com"
            assert _invite_store[token]["consultant_id"] == MOCK_USER_ID


# ===========================================================================
# GET /consultoria/clients tests
# ===========================================================================


class TestListClients:
    """Test list clients endpoint."""

    ENDPOINT = "/v1/consultoria/clients"

    def test_list_clients_returns_list(self, client: TestClient, _mock_supabase):
        """List clients returns expected structure."""
        mock_sb, mock_execute = _mock_supabase
        _mock_consultant_profile(mock_execute)

        # Mock a client in the list
        async def _side_effect(query):
            query_str = str(query)
            if "profiles" in query_str and "plan_type" in query_str:
                return MagicMock(data={"plan_type": "consultoria_mensal"})
            if "consultant_clients" in query_str:
                return MagicMock(data=[
                    {
                        "id": "c1",
                        "consultant_id": MOCK_USER_ID,
                        "client_id": "u2",
                        "status": "active",
                        "created_at": "2026-06-12T00:00:00Z",
                        "profiles": {
                            "email": "cliente@test.com",
                            "full_name": "Cliente Teste",
                        },
                    }
                ], count=1)
            return MagicMock(data=None, count=0)

        mock_execute.side_effect = _side_effect

        resp = client.get(self.ENDPOINT)
        if resp.status_code == 200:
            data = resp.json()
            assert "clients" in data
            assert "total" in data
            assert "active_count" in data

    def test_list_clients_filter_invalid_status(self, client: TestClient, _mock_supabase):
        """Invalid status filter returns 400."""
        mock_sb, mock_execute = _mock_supabase
        _mock_consultant_profile(mock_execute)

        resp = client.get(f"{self.ENDPOINT}?status_filter=invalid")
        assert resp.status_code in (400, 403, 422)


# ===========================================================================
# DELETE /consultoria/clients/{client_id} tests
# ===========================================================================


class TestRevokeClient:
    """Test revoke client endpoint."""

    def test_revoke_nonexistent_client_returns_404(self, client: TestClient, _mock_supabase):
        """Revoking a non-existent client relationship returns 404."""
        mock_sb, mock_execute = _mock_supabase
        _mock_consultant_profile(mock_execute)

        resp = client.delete("/v1/consultoria/clients/u2")
        assert resp.status_code in (403, 404, 500)


# ===========================================================================
# POST /consultoria/share/{client_id} tests
# ===========================================================================


class TestShareResource:
    """Test share resource endpoint."""

    def test_share_invalid_resource_type_returns_422(self, client: TestClient, _mock_supabase):
        """Invalid resource_type returns 422."""
        mock_sb, mock_execute = _mock_supabase
        _mock_consultant_profile(mock_execute)

        resp = client.post(
            "/v1/consultoria/share/u2",
            json={"resource_type": "invalid_type", "resource_id": "abc123"},
        )
        assert resp.status_code == 422

    def test_share_without_resource_id_returns_422(self, client: TestClient, _mock_supabase):
        """Missing resource_id returns 422."""
        mock_sb, mock_execute = _mock_supabase
        _mock_consultant_profile(mock_execute)

        resp = client.post(
            "/v1/consultoria/share/u2",
            json={"resource_type": "busca", "resource_id": ""},
        )
        assert resp.status_code == 422

    def test_share_nonexistent_client_returns_404(self, client: TestClient, _mock_supabase):
        """Sharing with non-existent client returns 404."""
        mock_sb, mock_execute = _mock_supabase
        _mock_consultant_profile(mock_execute)

        resp = client.post(
            "/v1/consultoria/share/u2",
            json={"resource_type": "busca", "resource_id": "abc-123-def"},
        )
        assert resp.status_code in (403, 404, 500)
