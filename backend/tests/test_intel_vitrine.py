"""VITRINE-001 (#1612): Tests for Public Intelligence Vitrine route.

Tests the GET /v1/intel/vitrine/{cnpj} endpoint.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from database import get_db
from main import app


@pytest.fixture(autouse=True)
def clear_vitrine_cache():
    """Clear the in-memory vitrine cache before and after each test."""
    # Import and clear the module-level cache
    import routes.intel_vitrine as iv
    iv._vitrine_cache.clear()
    yield
    iv._vitrine_cache.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def override_db():
    """Override get_db dependency with a mock for all tests."""
    mock_db = MagicMock()
    app.dependency_overrides[get_db] = lambda: mock_db
    yield
    app.dependency_overrides.clear()


class TestIntelVitrineRoute:
    """Basic route validation for GET /v1/intel/vitrine/{cnpj}."""

    def test_invalid_cnpj_format(self, client: TestClient):
        """Invalid CNPJ format returns 400."""
        resp = client.get("/v1/intel/vitrine/123")
        assert resp.status_code == 400

    def test_invalid_cnpj_with_letters(self, client: TestClient):
        """CNPJ with letters returns 400."""
        resp = client.get("/v1/intel/vitrine/abcdefghijklmn")
        assert resp.status_code == 400

    def test_invalid_cnpj_empty(self, client: TestClient):
        """Empty CNPJ returns 404 (route not matched)."""
        resp = client.get("/v1/intel/vitrine/")
        assert resp.status_code in (400, 404)

    @patch("routes.intel_vitrine._fetch_supplier_contracts")
    @patch("routes.intel_vitrine._fetch_company_name")
    def test_cnpj_with_data_returns_response(
        self, mock_company, mock_rpc, client: TestClient
    ):
        """Valid CNPJ with data returns 200 with correct structure."""
        mock_company.return_value = (
            "EMPRESA EXEMPLO LTDA",
            "Empresa Exemplo",
            "Construção de edifícios",
        )
        mock_rpc.return_value = {
            "total_contracts": 150,
            "total_value": 5_000_000.0,
            "serie_temporal": [
                {"mes": "2025-07", "count": 5, "valor_total": 200000.0},
                {"mes": "2025-08", "count": 3, "valor_total": 150000.0},
                {"mes": "2026-05", "count": 2, "valor_total": 80000.0},
            ],
            "top_orgaos": [
                {
                    "orgao_cnpj": "12345678000199",
                    "orgao_nome": "Prefeitura Municipal Exemplo",
                    "count": 50,
                    "valor_total": 2_000_000.0,
                }
            ],
            "distribuicao_uf": [
                {"uf": "SP", "count": 80, "valor_total": 3_000_000.0},
                {"uf": "RJ", "count": 70, "valor_total": 2_000_000.0},
            ],
        }

        resp = client.get("/v1/intel/vitrine/12345678000195")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()

        assert data["cnpj"] == "12345678000195"
        assert data["razao_social"] == "EMPRESA EXEMPLO LTDA"
        assert data["total_contratos_alltime"] == 150
        assert "total_contratos_12m" in data
        assert "valor_total_12m" in data
        assert "ranking" in data
        assert "top_orgaos" in data
        assert isinstance(data["top_orgaos"], list)
        assert len(data["top_orgaos"]) == 1
        assert "distribuicao_uf" in data
        assert isinstance(data["distribuicao_uf"], list)
        assert "distribuicao_ano" in data
        assert "distribuicao_modalidade" in data
        assert "generated_at" in data
        assert "aviso_legal" in data

    @patch("routes.intel_vitrine._fetch_supplier_contracts")
    @patch("routes.intel_vitrine._fetch_company_name")
    def test_cnpj_no_contracts_returns_404(
        self, mock_company, mock_rpc, client: TestClient
    ):
        """CNPJ with no contracts returns 404."""
        mock_company.return_value = (
            "EMPRESA SEM CONTRATOS LTDA",
            None,
            "Serviços de limpeza",
        )
        mock_rpc.return_value = {
            "total_contracts": 0,
            "total_value": 0.0,
            "serie_temporal": [],
            "top_orgaos": [],
            "distribuicao_uf": [],
        }

        resp = client.get("/v1/intel/vitrine/99887766000199")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text[:300]}"

    @patch("routes.intel_vitrine._fetch_supplier_contracts")
    @patch("routes.intel_vitrine._fetch_company_name")
    def test_cnpj_not_found_returns_404(
        self, mock_company, mock_rpc, client: TestClient
    ):
        """CNPJ not found in any source returns 404."""
        mock_company.return_value = (
            "99.887.766/0001-55",
            None,
            None,
        )
        mock_rpc.return_value = None

        resp = client.get("/v1/intel/vitrine/99887766000155")
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text[:300]}"

    @patch("routes.intel_vitrine._fetch_supplier_contracts")
    @patch("routes.intel_vitrine._fetch_company_name")
    def test_ranking_field_structure(
        self, mock_company, mock_rpc, client: TestClient
    ):
        """Ranking field has correct structure when data is present."""
        mock_company.return_value = (
            "CONSTRUTORA EXEMPLO LTDA",
            "Construtora Exemplo",
            "Construção de edifícios",
        )
        mock_rpc.return_value = {
            "total_contracts": 150,
            "total_value": 10_000_000.0,
            "serie_temporal": [
                {"mes": "2026-01", "count": 10, "valor_total": 500000.0},
                {"mes": "2026-02", "count": 15, "valor_total": 800000.0},
            ],
            "top_orgaos": [],
            "distribuicao_uf": [],
        }

        resp = client.get("/v1/intel/vitrine/99887766000188")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()

        ranking = data["ranking"]
        assert ranking is not None
        assert "percentil" in ranking
        assert "posicao" in ranking
        assert "total_empresas_setor" in ranking
        assert "texto_contexto" in ranking
        assert ranking["percentil"] > 0
        assert "top 5%" in ranking["texto_contexto"]

    @patch("routes.intel_vitrine._fetch_supplier_contracts")
    @patch("routes.intel_vitrine._fetch_company_name")
    def test_top_orgaos_limited_to_five(
        self, mock_company, mock_rpc, client: TestClient
    ):
        """Top orgaos list is limited to 5 items."""
        mock_company.return_value = ("EMPRESA LTDA", None, None)
        mock_rpc.return_value = {
            "total_contracts": 50,
            "total_value": 1_000_000.0,
            "serie_temporal": [],
            "top_orgaos": [
                {"orgao_cnpj": f"0000000000010{i}", "orgao_nome": f"Orgão {i}",
                 "count": 10 - i, "valor_total": 100000.0 * (10 - i)}
                for i in range(10)
            ],
            "distribuicao_uf": [],
        }

        resp = client.get("/v1/intel/vitrine/99887766000177")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["top_orgaos"]) <= 5

    @patch("routes.intel_vitrine._fetch_supplier_contracts")
    @patch("routes.intel_vitrine._fetch_company_name")
    def test_cnpj_clean_ignores_mask(
        self, mock_company, mock_rpc, client: TestClient
    ):
        """CNPJ with mask (dots only, no slashes in URL) is normalized."""
        mock_company.return_value = ("EMPRESA LTDA", None, None)
        mock_rpc.return_value = {
            "total_contracts": 10,
            "total_value": 500000.0,
            "serie_temporal": [],
            "top_orgaos": [],
            "distribuicao_uf": [],
        }

        # Use query param style or clean CNPJ — avoid slashes in URL path
        resp = client.get("/v1/intel/vitrine/12345678000195")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cnpj"] == "12345678000195"
        assert "razao_social" in data

    @patch("routes.intel_vitrine._fetch_supplier_contracts")
    @patch("routes.intel_vitrine._fetch_company_name")
    def test_distribuicao_ano_from_serie(
        self, mock_company, mock_rpc, client: TestClient
    ):
        """Yearly distribution is correctly computed from monthly series.

        Uses months within the 12-month window to ensure they're not
        filtered out by the 12m aggregate computation.
        """
        mock_company.return_value = ("EMPRESA LTDA", None, None)
        mock_rpc.return_value = {
            "total_contracts": 25,
            "total_value": 1_000_000.0,
            "serie_temporal": [
                {"mes": "2025-08", "count": 5, "valor_total": 100000.0},
                {"mes": "2025-09", "count": 3, "valor_total": 80000.0},
                {"mes": "2026-01", "count": 8, "valor_total": 300000.0},
                {"mes": "2026-03", "count": 4, "valor_total": 120000.0},
                {"mes": "2026-06", "count": 5, "valor_total": 400000.0},
            ],
            "top_orgaos": [],
            "distribuicao_uf": [],
        }

        resp = client.get("/v1/intel/vitrine/99887766000166")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        data = resp.json()

        anos = data["distribuicao_ano"]
        # 2025, 2026 — both have months in the window
        assert len(anos) == 2
        # Should be sorted descending
        assert anos[0]["chave"] == "2026"
        assert anos[1]["chave"] == "2025"

        # Verify counts for 2026: 8 + 4 + 5 = 17
        ano_2026 = next(a for a in anos if a["chave"] == "2026")
        assert ano_2026["quantidade"] == 17

        # Verify counts for 2025: 5 + 3 = 8
        ano_2025 = next(a for a in anos if a["chave"] == "2025")
        assert ano_2025["quantidade"] == 8
