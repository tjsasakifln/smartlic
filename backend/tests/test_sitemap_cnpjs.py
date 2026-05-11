"""Tests for GET /v1/sitemap/cnpjs and /v1/sitemap/fornecedores-cnpj endpoints.

SEO-SITEMAP-MV-001: ambos endpoints agora consultam Materialized Views
(mv_sitemap_cnpjs, mv_sitemap_fornecedores) em vez de RPC + live tables.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Patch seed to empty for tests that focus on buyer-only logic
_NO_SEED = patch("routes.sitemap_cnpjs._SEED_SUPPLIER_CNPJS", [])


@pytest.fixture(autouse=True)
def _clear_cache():
    """Clear sitemap caches before each test."""
    from routes.sitemap_cnpjs import _sitemap_cache, _fornecedores_sitemap_cache
    _sitemap_cache.clear()
    _fornecedores_sitemap_cache.clear()
    yield
    _sitemap_cache.clear()
    _fornecedores_sitemap_cache.clear()


@pytest.fixture
def client():
    from startup.app_factory import create_app
    app = create_app()
    return TestClient(app)


def _mock_mv_data(rows: list[dict]):
    """Build a mock for MV queries:
    sb.table("mv_sitemap_<X>").select("cnpj").order("cnpj").range(offset, end).execute()
    Simula paginação de 1000 por página.
    """
    mock_sb = MagicMock()
    page_size = 1000
    next_offset = {"value": 0}

    def execute_paginated(*_args, **_kwargs):
        resp = MagicMock()
        start = next_offset["value"]
        resp.data = rows[start: start + page_size]
        next_offset["value"] += page_size
        return resp

    (
        mock_sb.table.return_value
        .select.return_value
        .order.return_value
        .range.return_value
        .execute
    ).side_effect = execute_paginated
    return mock_sb


class TestSitemapCnpjs:
    """Tests for /v1/sitemap/cnpjs via mv_sitemap_cnpjs."""

    @_NO_SEED
    @patch("supabase_client.get_supabase")
    def test_returns_cnpjs_from_mv(self, mock_get_sb, client):
        """MV returns CNPJs from pre-aggregated materialized view."""
        rows = [
            {"cnpj": "11111111000100"},
            {"cnpj": "22222222000200"},
            {"cnpj": "33333333000300"},
        ]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/cnpjs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert data["cnpjs"] == ["11111111000100", "22222222000200", "33333333000300"]

    @_NO_SEED
    @patch("supabase_client.get_supabase")
    def test_empty_mv(self, mock_get_sb, client):
        """Returns empty list when MV has no data and seed is empty."""
        mock_get_sb.return_value = _mock_mv_data([])

        resp = client.get("/v1/sitemap/cnpjs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cnpjs"] == []
        assert data["total"] == 0

    @patch("supabase_client.get_supabase")
    def test_seed_cnpjs_always_included(self, mock_get_sb, client):
        """Seed supplier CNPJs appear in result even when MV is empty."""
        mock_get_sb.return_value = _mock_mv_data([])

        resp = client.get("/v1/sitemap/cnpjs")
        assert resp.status_code == 200
        data = resp.json()
        from routes.sitemap_cnpjs import _SEED_SUPPLIER_CNPJS
        for cnpj in _SEED_SUPPLIER_CNPJS:
            assert cnpj in data["cnpjs"], f"Seed CNPJ {cnpj} missing from sitemap"
        assert data["total"] == len(_SEED_SUPPLIER_CNPJS)

    @patch("supabase_client.get_supabase")
    def test_seed_cnpjs_appear_first(self, mock_get_sb, client):
        """Seed supplier CNPJs appear before MV CNPJs in sitemap."""
        rows = [{"cnpj": "99999999000999"}]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/cnpjs")
        data = resp.json()
        from routes.sitemap_cnpjs import _SEED_SUPPLIER_CNPJS
        assert data["cnpjs"][:len(_SEED_SUPPLIER_CNPJS)] == _SEED_SUPPLIER_CNPJS
        assert "99999999000999" in data["cnpjs"]

    @_NO_SEED
    @patch("supabase_client.get_supabase")
    def test_filters_invalid_cnpjs(self, mock_get_sb, client):
        """Skips null and empty CNPJ values from MV."""
        rows = [
            {"cnpj": ""},
            {"cnpj": None},
            {"cnpj": "123"},  # too short
            {"cnpj": "44444444000400"},
        ]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/cnpjs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["cnpjs"] == ["44444444000400"]

    @patch("supabase_client.get_supabase")
    def test_cache_serves_second_request(self, mock_get_sb, client):
        """Second request returns identical data (cache hit).

        Nota: O call_count do mock inclui chamadas das probes de telemetria
        (stale data, empty data) que rodam mesmo em cache hit. O teste verifica
        que a resposta é idêntica, não o número exato de chamadas.
        """
        rows = [{"cnpj": "55555555000500"}]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp1 = client.get("/v1/sitemap/cnpjs")
        assert resp1.status_code == 200

        resp2 = client.get("/v1/sitemap/cnpjs")
        assert resp2.status_code == 200
        assert resp2.json() == resp1.json()

    @patch("supabase_client.get_supabase")
    def test_graceful_failure(self, mock_get_sb, client):
        """Returns empty response on Supabase error instead of 500."""
        mock_get_sb.side_effect = Exception("connection failed")

        resp = client.get("/v1/sitemap/cnpjs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cnpjs"] == []
        assert data["total"] == 0

    @patch("supabase_client.get_supabase")
    def test_response_schema(self, mock_get_sb, client):
        """Response has required fields with correct types."""
        rows = [{"cnpj": "66666666000600"}]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/cnpjs")
        data = resp.json()
        assert isinstance(data["cnpjs"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["updated_at"], str)

    @patch("supabase_client.get_supabase")
    def test_max_5000_cnpjs(self, mock_get_sb, client):
        """Respects _MAX_CNPJS limit even when MV has more rows."""
        rows = [{"cnpj": f"{i:014d}"} for i in range(6000)]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/cnpjs")
        data = resp.json()
        assert data["total"] <= 5000


# ---------------------------------------------------------------------------
# Tests for /v1/sitemap/fornecedores-cnpj via mv_sitemap_fornecedores
# ---------------------------------------------------------------------------

@pytest.fixture
def _clear_fornecedores_cache():
    from routes.sitemap_cnpjs import _fornecedores_sitemap_cache
    _fornecedores_sitemap_cache.clear()
    yield
    _fornecedores_sitemap_cache.clear()


class TestSitemapFornecedoresCnpj:
    """Tests for /v1/sitemap/fornecedores-cnpj via mv_sitemap_fornecedores."""

    @patch("supabase_client.get_supabase")
    def test_dedup_same_cnpj_single_row(self, mock_get_sb, client, _clear_fornecedores_cache):
        """MV já retorna CNPJs únicos — response não tem duplicatas."""
        rows = [
            {"cnpj": "11111111111111"},
            {"cnpj": "22222222222222"},
        ]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/fornecedores-cnpj")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["cnpjs"]) == 2
        assert len(set(data["cnpjs"])) == 2, "Response contains duplicate CNPJs"

    @patch("supabase_client.get_supabase")
    def test_data_from_mv_all_included(self, mock_get_sb, client, _clear_fornecedores_cache):
        """MV retorna todos os CNPJs sem duplicates (pre-agregação)."""
        rows = [
            {"cnpj": "11111111111111"},
            {"cnpj": "22222222222222"},
            {"cnpj": "33333333333333"},
        ]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/fornecedores-cnpj")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["cnpjs"]) == 3
        assert len(set(data["cnpjs"])) == 3

    @patch("supabase_client.get_supabase")
    def test_filters_invalid_cnpjs(self, mock_get_sb, client, _clear_fornecedores_cache):
        """Skips non-14-digit CNPJ values from MV."""
        rows = [
            {"cnpj": ""},
            {"cnpj": None},
            {"cnpj": "123"},
            {"cnpj": "ABCDEFGHIJKLMN"},
            {"cnpj": "44444444444444"},
        ]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/fornecedores-cnpj")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["cnpjs"] == ["44444444444444"]

    @patch("supabase_client.get_supabase")
    def test_max_5000_fornecedores(self, mock_get_sb, client, _clear_fornecedores_cache):
        """Respects _MAX_FORNECEDORES_CNPJS cap."""
        rows = [{"cnpj": f"{i:014d}"} for i in range(6000)]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/fornecedores-cnpj")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] <= 5000
        assert len(data["cnpjs"]) <= 5000

    @patch("supabase_client.get_supabase")
    def test_graceful_failure(self, mock_get_sb, client, _clear_fornecedores_cache):
        """Returns empty response on Supabase error."""
        mock_get_sb.side_effect = Exception("connection failed")

        resp = client.get("/v1/sitemap/fornecedores-cnpj")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cnpjs"] == []
        assert data["total"] == 0

    @patch("supabase_client.get_supabase")
    def test_response_schema(self, mock_get_sb, client, _clear_fornecedores_cache):
        """Response has cnpjs, total, updated_at fields."""
        rows = [{"cnpj": "66666666666666"}]
        mock_get_sb.return_value = _mock_mv_data(rows)

        resp = client.get("/v1/sitemap/fornecedores-cnpj")
        data = resp.json()
        assert isinstance(data["cnpjs"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["updated_at"], str)
