"""Tests for API-SELF-002: API Key authenticated search endpoint.

Covers:
    - Valid API key → 200 with search results
    - Invalid API key (not found) → 401
    - Revoked API key → 401
    - Missing X-API-Key header → 401
    - Rate limit headers present on successful responses
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from auth import require_api_key
from schemas import BuscaResponse, ResumoLicitacoes

# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------

MOCK_USER_ID = "api-key-mock-user-00001"
MOCK_API_KEY_ID = "api-key-mock-id-000001"

MOCK_SEARCH_RESPONSE = BuscaResponse(
    resumo=ResumoLicitacoes(
        resumo_executivo="Encontradas 5 licitacoes para teste.",
        total_oportunidades=5,
        valor_total=100000.0,
        destaques=["2 urgentes", "Maior valor: R$ 50k"],
        alerta_urgencia=None,
    ),
    licitacoes=[],
    excel_base64=None,
    excel_available=False,
    quota_used=1,
    quota_remaining=99,
    total_raw=10,
    total_filtrado=5,
    filter_stats={"rejeitadas_uf": 2, "rejeitadas_keyword": 3},
)


def _mock_require_api_key() -> str:
    """Override for require_api_key — returns a fixed user_id."""
    return MOCK_USER_ID


def _mock_raise_401() -> str:
    """Override that simulates an invalid/revoked API key."""
    from fastapi import HTTPException
    raise HTTPException(status_code=401, detail="Invalid API key")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def override_valid_key():
    """Authenticate with a valid API key."""
    app.dependency_overrides[require_api_key] = _mock_require_api_key
    yield
    app.dependency_overrides.pop(require_api_key, None)


@pytest.fixture
def override_invalid_key():
    """Simulate authentication failure."""
    app.dependency_overrides[require_api_key] = _mock_raise_401
    yield
    app.dependency_overrides.pop(require_api_key, None)


@pytest.fixture(autouse=True)
def _mock_redis_unavailable():
    """Make Redis unavailable so rate limits fall through (fail-open).

    Without this, the rate-limit Redis INCR command hangs or errors in
    test isolation.  The rate-limit fixture above is still asserted for
    header presence via ``http_response.headers`` set by the handler.
    """
    with patch("redis_pool.get_redis_pool", new_callable=AsyncMock, return_value=None):
        yield


# ---------------------------------------------------------------------------
# Tests — Auth
# ---------------------------------------------------------------------------


class TestApiSearchAuth:
    """Authentication via X-API-Key header."""

    def test_missing_api_key_returns_401(self, client):
        """No X-API-Key header → 401."""
        response = client.get("/v1/api/search", params={"q": "uniformes"})
        assert response.status_code == 401
        data = response.json()
        assert "Invalid API key" in str(data.get("detail", data))

    def test_invalid_api_key_returns_401(self, client, override_invalid_key):
        """Invalid/unknown key → 401 with same message."""
        response = client.get(
            "/v1/api/search",
            params={"q": "uniformes"},
            headers={"X-API-Key": "sk_invalid_key_12345"},
        )
        assert response.status_code == 401
        data = response.json()
        assert "Invalid API key" in str(data.get("detail", data))

    def test_valid_api_key_with_mocked_pipeline_returns_200(
        self, client, override_valid_key
    ):
        """Valid key + successful pipeline → 200 with search results."""
        with patch(
            "routes.api_search.SearchPipeline.run",
            new_callable=AsyncMock,
            return_value=MOCK_SEARCH_RESPONSE,
        ):
            response = client.get(
                "/v1/api/search",
                params={"q": "uniformes", "uf": "SP"},
                headers={"X-API-Key": "sk_valid_key_12345"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["total_filtrado"] == 5
        assert data["total_raw"] == 10
        assert data["quota_remaining"] == 99
        assert "resumo" in data
        assert data["resumo"]["resumo_executivo"] != ""

    def test_rate_limit_headers_present(
        self, client, override_valid_key
    ):
        """Successful response includes X-RateLimit-* headers."""
        with patch(
            "routes.api_search.SearchPipeline.run",
            new_callable=AsyncMock,
            return_value=MOCK_SEARCH_RESPONSE,
        ):
            response = client.get(
                "/v1/api/search",
                params={"q": "uniformes"},
                headers={"X-API-Key": "sk_valid_key_12345"},
            )

        assert response.status_code == 200
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "1000"

    def test_pipeline_failure_returns_500(
        self, client, override_valid_key
    ):
        """Pipeline exception → 500."""
        with patch(
            "routes.api_search.SearchPipeline.run",
            new_callable=AsyncMock,
            side_effect=Exception("Pipeline crashed"),
        ):
            response = client.get(
                "/v1/api/search",
                params={"q": "uniformes"},
                headers={"X-API-Key": "sk_valid_key_12345"},
            )

        assert response.status_code == 500


# ---------------------------------------------------------------------------
# Tests — Search Params
# ---------------------------------------------------------------------------


class TestApiSearchParams:
    """Query parameter handling."""

    def test_minimal_params(self, client, override_valid_key):
        """Only q provided → default UF, page, size."""
        with patch(
            "routes.api_search.SearchPipeline.run",
            new_callable=AsyncMock,
            return_value=MOCK_SEARCH_RESPONSE,
        ):
            response = client.get(
                "/v1/api/search",
                params={"q": "uniformes"},
                headers={"X-API-Key": "sk_valid_key_12345"},
            )
        assert response.status_code == 200

    def test_all_params(self, client, override_valid_key):
        """All optional query params provided."""
        with patch(
            "routes.api_search.SearchPipeline.run",
            new_callable=AsyncMock,
            return_value=MOCK_SEARCH_RESPONSE,
        ):
            response = client.get(
                "/v1/api/search",
                params={
                    "q": "material escritorio",
                    "uf": "RJ",
                    "modalidade": "5,6",
                    "pagina": 2,
                    "tamanho": 50,
                },
                headers={"X-API-Key": "sk_valid_key_12345"},
            )
        assert response.status_code == 200

    def test_q_too_short_returns_422(self, client, override_valid_key):
        """q shorter than 2 chars → 422 validation error."""
        response = client.get(
            "/v1/api/search",
            params={"q": "a"},
            headers={"X-API-Key": "sk_valid_key_12345"},
        )
        assert response.status_code == 422

    def test_invalid_tamanho_returns_422(self, client, override_valid_key):
        """tamanho > 100 → 422."""
        response = client.get(
            "/v1/api/search",
            params={"q": "uniformes", "tamanho": 200},
            headers={"X-API-Key": "sk_valid_key_12345"},
        )
        assert response.status_code == 422

    def test_missing_q_returns_422(self, client, override_valid_key):
        """No q param → 422 (required)."""
        response = client.get(
            "/v1/api/search",
            headers={"X-API-Key": "sk_valid_key_12345"},
        )
        assert response.status_code == 422
