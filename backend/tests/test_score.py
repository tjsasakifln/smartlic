"""SCORE-001 (#1614): Tests for SmartLic Score API routes."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestScoreStatus:
    """Test GET /v1/intel/score/status endpoint."""

    def test_score_status_returns_ok(self, client: TestClient):
        """Status endpoint returns 200 with model_ready and feature_enabled."""
        resp = client.get("/v1/intel/score/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "model_ready" in data
        assert "feature_enabled" in data


class TestScoreBid:
    """Test POST /v1/intel/score endpoint (admin-only)."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Unauthenticated request returns 401."""
        resp = client.post(
            "/v1/intel/score",
            json={"bid_id": "test-123", "cnpj": "12345678901234"},
        )
        assert resp.status_code in (401, 403)

    def test_feature_disabled_returns_503(self, client: TestClient):
        """When feature flag is off, return 503."""
        with patch("routes.score.get_feature_flag", return_value=False):
            from routes.score import require_admin

            app.dependency_overrides[require_admin] = lambda: {"sub": "admin"}
            resp = client.post(
                "/v1/intel/score",
                json={"bid_id": "test-123", "cnpj": "12345678901234"},
            )
            app.dependency_overrides.clear()
            assert resp.status_code == 503


class TestScoreBatch:
    """Test POST /v1/intel/score/batch endpoint (admin-only)."""

    def test_unauthenticated_returns_401(self, client: TestClient):
        """Unauthenticated batch request returns 401."""
        resp = client.post(
            "/v1/intel/score/batch",
            json={
                "cnpj": "12345678901234",
                "bids": [{"bid_id": "test-1", "cnpj": "12345678901234"}],
            },
        )
        assert resp.status_code in (401, 403)

    def test_empty_bids_rejected(self, client: TestClient):
        """Empty bids list should be rejected."""
        with patch("routes.score.get_feature_flag", return_value=True):
            from routes.score import require_admin

            app.dependency_overrides[require_admin] = lambda: {"sub": "admin"}
            resp = client.post(
                "/v1/intel/score/batch",
                json={"cnpj": "12345678901234", "bids": []},
            )
            app.dependency_overrides.clear()
            assert resp.status_code == 422


class TestScoreSchemas:
    """Test score Pydantic schemas."""

    def test_score_request_validation(self):
        """ScoreRequest validates CNPJ length."""
        from schemas.score import ScoreRequest

        with pytest.raises(Exception):
            ScoreRequest(bid_id="test", cnpj="123")  # too short

    def test_score_response_model(self):
        """ScoreResponse has expected fields."""
        from schemas.score import ScoreResponse

        resp = ScoreResponse(
            bid_id="test-123",
            cnpj="12345678901234",
            win_probability=0.75,
            score_available=True,
            model_version="v1",
        )
        assert resp.win_probability == 0.75
        assert resp.score_available is True

    def test_batch_score_response_model(self):
        """BatchScoreResponse has expected fields."""
        from schemas.score import BatchScoreResponse, ScoreResponse

        resp = BatchScoreResponse(
            cnpj="12345678901234",
            scores=[
                ScoreResponse(
                    bid_id="test-1",
                    cnpj="12345678901234",
                    win_probability=0.8,
                    score_available=True,
                    model_version="v1",
                )
            ],
            mean_probability=0.8,
            model_version="v1",
        )
        assert resp.mean_probability == 0.8
        assert len(resp.scores) == 1
