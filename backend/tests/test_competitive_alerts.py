"""COMPINT-012 (#1666): Tests for Competitive Alerts CRUD and detection job.

Covers:
  - POST /v1/intel-concorrente/alerts — create alert
  - GET /v1/intel-concorrente/alerts — list user's alerts
  - DELETE /v1/intel-concorrente/alerts/{id} — delete alert
  - Validation: invalid CNPJ, invalid type
  - ARQ detection job: run_competitive_alert_detection
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth import require_auth
from main import app

MOCK_USER = {"id": "user-123", "email": "test@example.com"}


def _override_auth():
    return MOCK_USER


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _setup_auth():
    app.dependency_overrides[require_auth] = _override_auth
    yield
    app.dependency_overrides.clear()


class TestCompetitiveAlertsCRUD:

    def test_create_alert_success(self, client):
        """POST creates alert and returns 201 with alert data."""
        with patch("routes.competitive_intel.sb_execute") as mock_sb:
            mock_sb.side_effect = [
                MagicMock(data={
                    "id": "alert-123",
                    "user_id": "user-123",
                    "competitor_cnpj": "12345678000199",
                    "alert_type": "new_contract",
                    "enabled": True,
                    "created_at": "2026-06-12T00:00:00Z",
                }),
            ]
            resp = client.post(
                "/v1/intel-concorrente/alerts",
                json={
                    "competitor_cnpj": "12345678000199",
                    "alert_type": "new_contract",
                    "enabled": True,
                },
            )
            assert resp.status_code == 201
            body = resp.json()
            assert body["id"] == "alert-123"
            assert body["competitor_cnpj"] == "12345678000199"
            assert body["alert_type"] == "new_contract"

    def test_create_alert_invalid_cnpj(self, client):
        """Invalid CNPJ returns 400."""
        resp = client.post(
            "/v1/intel-concorrente/alerts",
            json={
                "competitor_cnpj": "123",
                "alert_type": "new_contract",
            },
        )
        assert resp.status_code == 400

    def test_create_alert_invalid_type(self, client):
        """Invalid alert_type returns 400."""
        resp = client.post(
            "/v1/intel-concorrente/alerts",
            json={
                "competitor_cnpj": "12345678000199",
                "alert_type": "invalid_type_xyz",
            },
        )
        assert resp.status_code == 400

    def test_list_alerts_success(self, client):
        """GET returns list of alerts."""
        with patch("routes.competitive_intel.sb_execute") as mock_sb:
            mock_sb.side_effect = [
                MagicMock(data=[
                    {
                        "id": "alert-1",
                        "user_id": "user-123",
                        "competitor_cnpj": "12345678000199",
                        "alert_type": "new_contract",
                        "enabled": True,
                        "created_at": "2026-06-12T00:00:00Z",
                    },
                    {
                        "id": "alert-2",
                        "user_id": "user-123",
                        "competitor_cnpj": "98765432000188",
                        "alert_type": "new_uf",
                        "enabled": True,
                        "created_at": "2026-06-11T00:00:00Z",
                    },
                ]),
            ]
            resp = client.get("/v1/intel-concorrente/alerts")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 2
            assert len(body["alerts"]) == 2
            assert body["alerts"][0]["competitor_cnpj"] == "12345678000199"

    def test_list_alerts_empty(self, client):
        """GET returns empty list when no alerts."""
        with patch("routes.competitive_intel.sb_execute") as mock_sb:
            mock_sb.side_effect = [
                MagicMock(data=[]),
            ]
            resp = client.get("/v1/intel-concorrente/alerts")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 0
            assert body["alerts"] == []

    def test_delete_alert_success(self, client):
        """DELETE removes alert and returns 204."""
        with patch("routes.competitive_intel.sb_execute") as mock_sb:
            # First call: ownership check returns data
            # Second call: delete succeeds
            mock_sb.side_effect = [
                MagicMock(data={"id": "alert-123"}),
                MagicMock(data=None),
            ]
            resp = client.delete("/v1/intel-concorrente/alerts/alert-123")
            assert resp.status_code == 204

    def test_delete_alert_not_found(self, client):
        """DELETE on non-existent alert returns 404."""
        with patch("routes.competitive_intel.sb_execute") as mock_sb:
            mock_sb.side_effect = [
                MagicMock(data=None),  # ownership check returns empty
            ]
            resp = client.delete("/v1/intel-concorrente/alerts/alert-999")
            assert resp.status_code == 404

    def test_alert_endpoints_require_auth(self, client):
        """All alert endpoints return 401 without auth."""
        app.dependency_overrides.clear()
        endpoints = [
            ("POST", "/v1/intel-concorrente/alerts", {
                "competitor_cnpj": "12345678000199",
                "alert_type": "new_contract",
            }),
            ("GET", "/v1/intel-concorrente/alerts", None),
            ("DELETE", "/v1/intel-concorrente/alerts/alert-123", None),
        ]
        for method, path, body in endpoints:
            if method == "POST":
                resp = client.post(path, json=body)
            elif method == "GET":
                resp = client.get(path)
            else:
                resp = client.delete(path)
            assert resp.status_code == 401, f"{method} {path} should return 401"


class TestCompetitiveAlertDetectionJob:

    @pytest.mark.asyncio
    async def test_detection_no_alerts(self):
        """Detection returns early when no alerts exist."""
        from jobs.cron.competitive_alert_job import run_competitive_alert_detection

        with patch("supabase_client.sb_execute") as mock_sb:
            mock_sb.return_value = MagicMock(data=[])
            result = await run_competitive_alert_detection()
            assert result["processed"] == 0
            assert result["reason"] == "no_alerts"

    @pytest.mark.asyncio
    async def test_detection_with_alerts_no_contracts(self):
        """Detection processes alerts but finds no new contracts."""
        from jobs.cron.competitive_alert_job import run_competitive_alert_detection

        with patch("supabase_client.sb_execute") as mock_sb:
            # First call: fetch alerts — returns enabled alerts
            # Second call: fetch contracts — returns empty
            mock_sb.side_effect = [
                MagicMock(data=[
                    {
                        "id": "alert-1",
                        "user_id": "user-123",
                        "competitor_cnpj": "12345678000199",
                        "alert_type": "new_contract",
                        "enabled": True,
                        "metadata": {},
                    },
                ]),
                MagicMock(data=[]),  # no new contracts
            ]
            result = await run_competitive_alert_detection()
            assert result["processed"] == 1
            assert result["events_found"] == 0
