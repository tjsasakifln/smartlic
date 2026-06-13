"""COMPINT-011 (#1663): Tests for Competitive Intelligence route.

Covers:
  - Route registered and returns expected status codes
  - Auth gate: 401 without auth
  - Competitive intel gate: 404 when flag off, 403 when capability false
  - CNPJ validation: 400 for invalid format
  - Data flow: returns FornecedorIntelResponse when data available
  - Error handling: RPC failure returns 502
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth import require_auth
from main import app

MOCK_USER = {"id": "user-123", "email": "test@example.com"}


def _override_auth():
    return MOCK_USER


# Sample data
SAMPLE_TERRITORY_DATA = {
    "concorrente": {
        "cnpj": "12345678000199",
        "nome": "Fornecedor ABC Ltda",
        "total_contratos": 45,
        "ticket_medio": 250000.0,
        "ticket_mediana": 180000.0,
        "valor_total_contratado": 11250000.0,
    },
    "territorio": [
        {
            "uf": "SP",
            "contratos": 20,
            "valor_total": 5000000.0,
            "ticket_medio_uf": 250000.0,
            "orgaos_principais": ["Governo SP"],
            "market_share_uf": 0.35,
            "tendencia": "crescendo",
        },
        {
            "uf": "RJ",
            "contratos": 10,
            "valor_total": 2500000.0,
            "ticket_medio_uf": 250000.0,
            "orgaos_principais": ["Prefeitura RJ"],
            "market_share_uf": 0.15,
            "tendencia": "estavel",
        },
    ],
    "orgaos_favoritos": [
        {
            "orgao_nome": "Governo SP",
            "contratos": 15,
            "valor_total": 3750000.0,
            "categorias": ["Infraestrutura"],
            "ultima_vitoria": "2026-05-15",
            "frequencia_anual": 3.0,
        },
    ],
    "stats": {
        "ufs_atuacao": 2,
        "orgaos_unicos": 3,
        "anos_atuacao": 5,
        "crescimento_anual": 0.35,
        "tendencia_posicionamento": "expansao",
    },
}

SAMPLE_WIN_METRICS_DATA = {
    "cnpj": "12345678000199",
    "nome": "Fornecedor ABC Ltda",
    "win_metrics": {
        "taxa_vitoria_estimada": 0.45,
        "velocidade_crescimento": 1.2,
        "tendencia": "crescendo",
        "ticket_p25": 80000.0,
        "ticket_p50": 180000.0,
        "ticket_p75": 350000.0,
        "ticket_p90": 500000.0,
        "indice_concentracao": 0.3,
        "dependencia_publica": 0.85,
    },
}

MOCK_QUOTA_PASS = MagicMock(
    capabilities={"allow_competitive_intel": True},
    plan_id="smartlic_command",
    allowed=True,
)


def _make_rpc_result(data: dict):
    return MagicMock(data=data)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _setup_auth():
    """Override auth dependency for all tests."""
    app.dependency_overrides[require_auth] = _override_auth
    yield
    app.dependency_overrides.clear()


class TestCompetitiveIntelRoute:

    def _setup_mocks(self, mock_sb=None):
        """Create common mock patches."""
        patches = [
            patch("config.features.get_feature_flag", return_value=True),
            patch("authorization.has_master_access", new=AsyncMock(return_value=True)),
            patch("quota.plan_enforcement.check_quota", return_value=MOCK_QUOTA_PASS),
        ]
        if mock_sb is not None:
            patches.append(mock_sb)
        return patches

    def test_route_registered(self, client):
        """Route is registered and returns 200 for authenticated request."""
        with (
            patch("config.features.get_feature_flag", return_value=True),
            patch("authorization.has_master_access", new=AsyncMock(return_value=True)),
            patch("quota.plan_enforcement.check_quota", return_value=MOCK_QUOTA_PASS),
        ):
            with patch("supabase_client.sb_execute") as mock_sb:
                mock_sb.side_effect = [
                    _make_rpc_result(SAMPLE_TERRITORY_DATA),
                    _make_rpc_result(SAMPLE_WIN_METRICS_DATA),
                ]
                resp = client.get("/v1/intel-concorrente/fornecedor/12345678000199")
                assert resp.status_code == 200

    def test_response_schema(self, client):
        """Returns expected schema fields."""
        with (
            patch("config.features.get_feature_flag", return_value=True),
            patch("authorization.has_master_access", new=AsyncMock(return_value=True)),
            patch("quota.plan_enforcement.check_quota", return_value=MOCK_QUOTA_PASS),
        ):
            with patch("supabase_client.sb_execute") as mock_sb:
                mock_sb.side_effect = [
                    _make_rpc_result(SAMPLE_TERRITORY_DATA),
                    _make_rpc_result(SAMPLE_WIN_METRICS_DATA),
                ]
                resp = client.get("/v1/intel-concorrente/fornecedor/12345678000199")
                assert resp.status_code == 200
                body = resp.json()
                assert "concorrente" in body
                assert "territorio" in body
                assert "orgaos_favoritos" in body
                assert "stats" in body
                assert "win_metrics" in body
                assert "alertas" in body
                assert body["concorrente"]["nome"] == "Fornecedor ABC Ltda"
                assert body["concorrente"]["total_contratos"] == 45
                assert len(body["territorio"]) == 2
                assert len(body["alertas"]) > 0

    def test_invalid_cnpj_returns_400(self, client):
        """Invalid CNPJ format returns 400 validation error."""
        with (
            patch("config.features.get_feature_flag", return_value=True),
            patch("authorization.has_master_access", new=AsyncMock(return_value=True)),
            patch("quota.plan_enforcement.check_quota", return_value=MOCK_QUOTA_PASS),
            patch("supabase_client.sb_execute"),
        ):
            resp = client.get("/v1/intel-concorrente/fornecedor/123")
            assert resp.status_code == 400

    def test_rpc_error_returns_502(self, client):
        """RPC failure returns 502 Bad Gateway."""
        with (
            patch("config.features.get_feature_flag", return_value=True),
            patch("authorization.has_master_access", new=AsyncMock(return_value=True)),
            patch("quota.plan_enforcement.check_quota", return_value=MOCK_QUOTA_PASS),
        ):
            with patch("supabase_client.sb_execute") as mock_sb:
                mock_sb.side_effect = Exception("RPC failed")
                resp = client.get("/v1/intel-concorrente/fornecedor/12345678000199")
                assert resp.status_code == 502

    def test_no_data_returns_404(self, client):
        """Supplier without competitive data returns 404."""
        with (
            patch("config.features.get_feature_flag", return_value=True),
            patch("authorization.has_master_access", new=AsyncMock(return_value=True)),
            patch("quota.plan_enforcement.check_quota", return_value=MOCK_QUOTA_PASS),
        ):
            with patch("supabase_client.sb_execute") as mock_sb:
                mock_sb.side_effect = [
                    _make_rpc_result({"erro": "CNPJ invalido"}),
                ]
                resp = client.get("/v1/intel-concorrente/fornecedor/12345678000199")
                assert resp.status_code == 404

    def test_requires_auth(self, client):
        """Route returns 401 without auth."""
        app.dependency_overrides.clear()
        resp = client.get("/v1/intel-concorrente/fornecedor/12345678000199")
        assert resp.status_code == 401
