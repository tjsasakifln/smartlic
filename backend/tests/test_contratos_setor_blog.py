"""Tests for GET /v1/blog/stats/contratos/{setor_id} (Wave 3.1)."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from main import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def _make_mock_sb(rows):
    mock_resp = MagicMock()
    mock_resp.data = rows
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_resp
    return mock_sb


@pytest.fixture(autouse=True)
def clear_cache():
    from routes.blog_stats import _blog_cache
    _blog_cache.clear()
    yield
    _blog_cache.clear()


class TestContratosSetorBlogStats:
    def test_valid_sector_returns_stats(self, client):
        rows = [
            {
                "ni_fornecedor": "11111111000100",
                "nome_fornecedor": "TechCorp",
                "orgao_cnpj": "99999999000100",
                "orgao_nome": "Min Educacao",
                "valor_global": 100000.0,
                "data_assinatura": "2026-03-20",
                "objeto_contrato": "Fornecimento de computadores e equipamentos de informatica",
                "uf": "SP",
            },
        ]

        with patch("supabase_client.get_supabase", return_value=_make_mock_sb(rows)):
            resp = client.get("/v1/blog/stats/contratos/informatica")

        assert resp.status_code == 200
        data = resp.json()
        assert data["sector_id"] == "informatica"
        assert "total_contracts" in data
        assert "total_value" in data
        assert "top_orgaos" in data
        assert "top_fornecedores" in data
        assert "monthly_trend" in data
        assert "by_uf" in data
        assert "last_updated" in data

    def test_invalid_sector_returns_404(self, client):
        resp = client.get("/v1/blog/stats/contratos/nonexistent_sector")
        assert resp.status_code == 404

    def test_hyphenated_sector_slug(self, client):
        rows = [
            {
                "ni_fornecedor": "11111111000100",
                "nome_fornecedor": "RodCorp",
                "orgao_cnpj": "99999999000100",
                "orgao_nome": "DNIT",
                "valor_global": 500000.0,
                "data_assinatura": "2026-03-20",
                "objeto_contrato": "Obras de pavimentacao rodoviaria",
                "uf": "GO",
            },
        ]

        with patch("supabase_client.get_supabase", return_value=_make_mock_sb(rows)):
            resp = client.get("/v1/blog/stats/contratos/engenharia-rodoviaria")

        assert resp.status_code == 200
        data = resp.json()
        assert data["sector_id"] == "engenharia_rodoviaria"

    def test_monthly_trend_has_12_entries(self, client):
        rows = [
            {
                "ni_fornecedor": "11111111000100",
                "nome_fornecedor": "TechCorp",
                "orgao_cnpj": "99999999000100",
                "orgao_nome": "Min Ed",
                "valor_global": 100000.0,
                "data_assinatura": "2026-03-20",
                "objeto_contrato": "Computadores informatica",
                "uf": "SP",
            },
        ]

        with patch("supabase_client.get_supabase", return_value=_make_mock_sb(rows)):
            resp = client.get("/v1/blog/stats/contratos/informatica")

        assert resp.status_code == 200
        assert len(resp.json()["monthly_trend"]) == 12
