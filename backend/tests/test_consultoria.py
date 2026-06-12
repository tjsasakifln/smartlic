"""CONSULT-001 (#1613): Tests for Consultant Seats routes."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestConsultoriasRoutes:
    _BASE = "/v1/consultoria"

    def test_route_registered(self, client: TestClient):
        resp = client.post(f"{self._BASE}/invite-client", json={"client_email": "test@example.com"})
        assert resp.status_code in (401, 403, 422, 500)

    def test_list_clients_needs_auth(self, client: TestClient):
        resp = client.get(f"{self._BASE}/clients")
        assert resp.status_code == 401

    def test_revoke_client_needs_auth(self, client: TestClient):
        resp = client.delete(f"{self._BASE}/clients/some-id")
        assert resp.status_code == 401

    def test_share_needs_auth(self, client: TestClient):
        resp = client.post(f"{self._BASE}/share/some-id", json={"resource_type": "busca", "resource_id": "550e8400-e29b-41d4-a716-446655440000"})
        assert resp.status_code == 401

    def test_list_shared_needs_auth(self, client: TestClient):
        resp = client.get(f"{self._BASE}/shared/some-id")
        assert resp.status_code == 401

    def test_invalid_resource_type(self, client: TestClient):
        resp = client.post(f"{self._BASE}/share/some-id", json={"resource_type": "invalid_type", "resource_id": "some-id"})
        assert resp.status_code in (401, 422)

    def test_invite_without_email(self, client: TestClient):
        resp = client.post(f"{self._BASE}/invite-client", json={})
        assert resp.status_code in (401, 422)
