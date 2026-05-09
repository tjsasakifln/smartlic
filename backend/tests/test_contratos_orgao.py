"""Tests for GET /v1/contratos/orgao/{cnpj}/stats (Wave 2.3)."""

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
    empty_resp = MagicMock()
    empty_resp.data = []
    mock_sb = MagicMock()
    # DATA-CAP-001: route now calls paginate_full → .order().range(s,e).execute()
    # First call returns rows; subsequent empty/short response ends pagination loop.
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.range.return_value.execute.side_effect = [
        mock_resp, empty_resp, empty_resp
    ]
    # Backwards-compat with any caller still chaining .limit.
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value = mock_resp
    return mock_sb


@pytest.fixture(autouse=True)
def clear_cache():
    from routes.contratos_publicos import _orgao_contratos_cache
    _orgao_contratos_cache.clear()
    yield
    _orgao_contratos_cache.clear()


class TestOrgaoContratosStats:
    def test_valid_cnpj_returns_stats(self, client):
        rows = [
            {
                "ni_fornecedor": "11111111000100",
                "nome_fornecedor": "Fornecedor Alpha",
                "orgao_cnpj": "99999999000100",
                "orgao_nome": "Secretaria de Educacao",
                "valor_global": 50000.0,
                "data_assinatura": "2026-03-15",
                "objeto_contrato": "Fornecimento de material escolar",
            },
            {
                "ni_fornecedor": "22222222000100",
                "nome_fornecedor": "Fornecedor Beta",
                "orgao_cnpj": "99999999000100",
                "orgao_nome": "Secretaria de Educacao",
                "valor_global": 30000.0,
                "data_assinatura": "2026-02-10",
                "objeto_contrato": "Servico de manutencao predial",
            },
        ]

        with patch("supabase_client.get_supabase", return_value=_make_mock_sb(rows)):
            resp = client.get("/v1/contratos/orgao/99999999000100/stats")

        assert resp.status_code == 200
        data = resp.json()
        assert data["orgao_cnpj"] == "99999999000100"
        assert data["orgao_nome"] == "Secretaria de Educacao"
        assert data["total_contracts"] == 2
        assert data["total_value"] == 80000.0
        assert data["avg_value"] == 40000.0
        assert len(data["top_fornecedores"]) == 2
        assert len(data["sample_contracts"]) == 2
        assert "aviso_legal" in data

    def test_invalid_cnpj_short_returns_400(self, client):
        resp = client.get("/v1/contratos/orgao/12345678901234/stats")
        # This is a valid 14-digit CNPJ format; it would try to query
        # Let's test actually invalid format
        resp = client.get("/v1/contratos/orgao/abcdefghijklmn/stats")
        assert resp.status_code == 400

    def test_empty_results_returns_404(self, client):
        with patch("supabase_client.get_supabase", return_value=_make_mock_sb([])):
            resp = client.get("/v1/contratos/orgao/88888888000100/stats")
        assert resp.status_code == 404

    def test_monthly_trend_has_12_entries(self, client):
        rows = [
            {
                "ni_fornecedor": "11111111000100",
                "nome_fornecedor": "Alpha",
                "orgao_cnpj": "77777777000100",
                "orgao_nome": "Orgao X",
                "valor_global": 10000.0,
                "data_assinatura": "2026-01-15",
                "objeto_contrato": "Servico teste",
            },
        ]
        with patch("supabase_client.get_supabase", return_value=_make_mock_sb(rows)):
            resp = client.get("/v1/contratos/orgao/77777777000100/stats")
        assert resp.status_code == 200
        assert len(resp.json()["monthly_trend"]) == 12
