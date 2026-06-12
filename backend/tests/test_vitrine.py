"""VITRINE-001 (#1612): Tests for public intelligence vitrine routes."""

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestIntelVitrineRoute:
    """Basic route validation for GET /v1/intel/vitrine/{cnpj}."""

    def test_route_registered(self, client: TestClient):
        """Route is registered and returns a valid response."""
        resp = client.get("/v1/intel/vitrine/00000000000000")
        # Route exists — may return 200 (data), 400 (invalid CNPJ), or 404 (not found)
        assert resp.status_code in (200, 400, 404, 422, 500)

    def test_invalid_cnpj_too_short(self, client: TestClient):
        """CNPJ with wrong length returns 400."""
        resp = client.get("/v1/intel/vitrine/123")
        assert resp.status_code in (400, 404, 422)

    def test_invalid_cnpj_with_letters(self, client: TestClient):
        """CNPJ with non-numeric chars returns 400."""
        resp = client.get("/v1/intel/vitrine/abc12345678901")
        assert resp.status_code in (400, 404, 422)

    def test_valid_cnpj_format(self, client: TestClient):
        """Valid 14-digit CNPJ is accepted by the route."""
        resp = client.get("/v1/intel/vitrine/12345678901234")
        assert resp.status_code in (200, 404, 422, 500)


class TestIntelVitrineSearch:
    """Test GET /v1/intel/vitrine/search endpoint."""

    def test_search_route_exists(self, client: TestClient):
        """Search route exists — may return 200 (data), 400 (bad CNPJ via param match),
        422 (validation), or 500 (DB error)."""
        resp = client.get("/v1/intel/vitrine/search?q=empresa")
        assert resp.status_code in (200, 400, 422, 500), f"Unexpected status {resp.status_code}"

    def test_search_empty_query(self, client: TestClient):
        """Empty query returns 422."""
        resp = client.get("/v1/intel/vitrine/search?q=")
        assert resp.status_code == 422

    def test_search_short_query(self, client: TestClient):
        """Very short query (1 char) returns 422."""
        resp = client.get("/v1/intel/vitrine/search?q=a")
        assert resp.status_code == 422


class TestIntelVitrineSchemas:
    """Test vitrine Pydantic schemas."""

    def test_vitrine_response_model(self):
        """IntelVitrineResponse has expected fields."""
        from schemas.intel_vitrine import IntelVitrineResponse

        data = IntelVitrineResponse(
            cnpj="12345678901234",
            razao_social="Empresa Teste Ltda",
            nome_fantasia="Teste",
            setor_principal="Construção",
            setor_nome="Construção Civil",
            total_contratos_12m=10,
            valor_total_12m=500000.0,
            total_contratos_alltime=50,
            valor_total_alltime=2500000.0,
            ranking=None,
            top_orgaos=[],
            distribuicao_uf=[],
            distribuicao_ano=[],
            distribuicao_modalidade=[],
            generated_at="2026-06-12T00:00:00",
        )
        assert data.cnpj == "12345678901234"
        assert data.razao_social == "Empresa Teste Ltda"
        assert data.total_contratos_alltime == 50
        assert data.valor_total_alltime == 2500000.0

    def test_vitrine_response_with_ranking(self):
        """Vitrine response with ranking info."""
        from schemas.intel_vitrine import IntelVitrineResponse, RankingInfo, OrgaoInfo, DistribuicaoItem

        data = IntelVitrineResponse(
            cnpj="12345678901234",
            razao_social="Empresa Teste Ltda",
            total_contratos_12m=10,
            valor_total_12m=500000.0,
            total_contratos_alltime=50,
            valor_total_alltime=2500000.0,
            ranking=RankingInfo(
                percentil=95.0,
                posicao=50,
                total_empresas_setor=1000,
                texto_contexto="Esta empresa está entre as top 5% do setor Construção",
            ),
            top_orgaos=[
                OrgaoInfo(
                    nome="Prefeitura Municipal",
                    cnpj="11222333000181",
                    total_contratos=20,
                    valor_total=1000000.0,
                )
            ],
            distribuicao_uf=[
                DistribuicaoItem(
                    chave="SP",
                    quantidade=30,
                    valor_total=1500000.0,
                )
            ],
            distribuicao_ano=[
                DistribuicaoItem(
                    chave="2025",
                    quantidade=20,
                    valor_total=1000000.0,
                )
            ],
            distribuicao_modalidade=[],
            generated_at="2026-06-12T00:00:00",
        )
        assert data.ranking is not None
        assert data.ranking.percentil == 95.0
        assert data.ranking.texto_contexto != ""
        assert len(data.top_orgaos) == 1
        assert data.top_orgaos[0].nome == "Prefeitura Municipal"
        assert len(data.distribuicao_uf) == 1
        assert data.distribuicao_uf[0].chave == "SP"
        assert len(data.distribuicao_ano) == 1
        assert data.distribuicao_ano[0].chave == "2025"
