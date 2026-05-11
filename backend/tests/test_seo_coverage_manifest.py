"""Tests for SEO-COVERAGE-MANIFEST-001: /v1/seo/coverage-manifest endpoint."""

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _clear_cache():
    from routes.seo_coverage_manifest import _manifest_cache
    _manifest_cache.clear()
    yield
    _manifest_cache.clear()


@pytest.fixture
def client():
    from startup.app_factory import create_app
    app = create_app()
    return TestClient(app)


def _mock_sb_with_rows(rows: list[dict]):
    mock_sb = MagicMock()
    resp = MagicMock()
    resp.data = rows
    (
        mock_sb.table.return_value
        .select.return_value
        .order.return_value
        .execute
    ).return_value = resp
    return mock_sb


class TestCoverageManifestEndpoint:
    """Tests for GET /v1/seo/coverage-manifest."""

    @patch("supabase_client.get_supabase")
    def test_returns_200_with_empty_manifest(self, mock_get_sb, client):
        mock_get_sb.return_value = _mock_sb_with_rows([])
        resp = client.get("/v1/seo/coverage-manifest")
        assert resp.status_code == 200
        body = resp.json()
        assert "entities" in body
        assert "total" in body
        assert body["total"] == 0

    @patch("supabase_client.get_supabase")
    def test_returns_manifest_with_entries(self, mock_get_sb, client):
        rows = [
            {
                "entity_type": "municipio",
                "entity_id": "sao-paulo-sp",
                "coverage_status": "full",
                "last_activity_at": "2026-04-01T00:00:00+00:00",
                "updated_at": "2026-05-11T06:00:00+00:00",
            },
            {
                "entity_type": "municipio",
                "entity_id": "guaranesia-mg",
                "coverage_status": "empty",
                "last_activity_at": None,
                "updated_at": "2026-05-11T06:00:00+00:00",
            },
        ]
        mock_get_sb.return_value = _mock_sb_with_rows(rows)
        resp = client.get("/v1/seo/coverage-manifest")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert "municipio" in body["entities"]
        assert body["entities"]["municipio"]["sao-paulo-sp"]["coverage_status"] == "full"
        assert body["entities"]["municipio"]["guaranesia-mg"]["coverage_status"] == "empty"

    @patch("supabase_client.get_supabase")
    def test_returns_cache_control_header(self, mock_get_sb, client):
        mock_get_sb.return_value = _mock_sb_with_rows([])
        resp = client.get("/v1/seo/coverage-manifest")
        assert "Cache-Control" in resp.headers
        assert "max-age=3600" in resp.headers["Cache-Control"]

    @patch("supabase_client.get_supabase")
    def test_in_memory_cache_prevents_second_db_call(self, mock_get_sb, client):
        mock_get_sb.return_value = _mock_sb_with_rows([])
        client.get("/v1/seo/coverage-manifest")
        client.get("/v1/seo/coverage-manifest")
        # supabase called only once (cache hit on second request)
        # get_supabase may be called from middleware/lifespan; check table was called once
        table_calls = mock_get_sb.return_value.table.call_count
        assert table_calls <= 1

    @patch("supabase_client.get_supabase")
    def test_graceful_fallback_on_db_error(self, mock_get_sb, client):
        mock_get_sb.side_effect = Exception("DB unavailable")
        resp = client.get("/v1/seo/coverage-manifest")
        # Should not 500 — returns empty manifest
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["entities"] == {}
