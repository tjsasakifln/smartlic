"""WIDGET-COMPINT-001: Tests for Competitive Intelligence Widget endpoint.

Tests cover:
  1. Each of 4 themes returns valid data
  2. Missing/invalid params return 400
  3. CORS headers present
  4. Rate limiting
  5. Cache headers
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient, ASGITransport

from main import app

SAMPLE_RPC_DATA = {
    "sector": "informatica",
    "uf": None,
    "window_months": 12,
    "total_contracts": 500,
    "total_value": 50000000.0,
    "top_fornecedores": [
        {
            "ni_fornecedor": "11222333000181",
            "nome_fornecedor": "Tech Solutions Ltda",
            "count": 45,
            "valor_total": 15000000.0,
            "avg_ticket": 333333.33,
        },
        {
            "ni_fornecedor": "44555666000199",
            "nome_fornecedor": "Dados & Sistemas S.A.",
            "count": 30,
            "valor_total": 10000000.0,
            "avg_ticket": 333333.33,
        },
        {
            "ni_fornecedor": "77888999000111",
            "nome_fornecedor": "Consultoria TI Brasil",
            "count": 20,
            "valor_total": 5000000.0,
            "avg_ticket": 250000.0,
        },
    ],
    "serie_temporal": [
        {"mes": "2025-07", "count": 40, "valor_total": 4000000.0},
        {"mes": "2025-08", "count": 42, "valor_total": 4200000.0},
        {"mes": "2025-09", "count": 38, "valor_total": 3800000.0},
        {"mes": "2025-10", "count": 45, "valor_total": 4500000.0},
        {"mes": "2025-11", "count": 50, "valor_total": 5000000.0},
        {"mes": "2025-12", "count": 48, "valor_total": 4800000.0},
        {"mes": "2026-01", "count": 52, "valor_total": 5200000.0},
        {"mes": "2026-02", "count": 55, "valor_total": 5500000.0},
        {"mes": "2026-03", "count": 50, "valor_total": 5000000.0},
        {"mes": "2026-04", "count": 48, "valor_total": 4800000.0},
        {"mes": "2026-05", "count": 55, "valor_total": 5500000.0},
        {"mes": "2026-06", "count": 60, "valor_total": 6000000.0},
    ],
    "top_orgaos": [
        {
            "orgao_cnpj": "12345678000190",
            "orgao_nome": "Secretaria de Tecnologia",
            "count": 25,
            "valor_total": 8000000.0,
        },
        {
            "orgao_cnpj": "98765432000110",
            "orgao_nome": "Ministério da Gestão",
            "count": 20,
            "valor_total": 6000000.0,
        },
    ],
    "generated_at": "2026-06-11T12:00:00Z",
}


@pytest.fixture
def clear_cache():
    """Clear the widget in-memory cache before each test."""
    from routes.widget_compint import _widget_cache

    _widget_cache.clear()


@pytest.fixture
def mock_rpc():
    """Mock the Supabase RPC call to return sample data."""
    mock_sb = MagicMock()
    mock_result = MagicMock()
    mock_result.data = SAMPLE_RPC_DATA
    mock_sb.rpc.return_value = mock_result

    with (
        patch("routes.widget_compint.get_supabase", return_value=mock_sb) as _mock_supabase,
        patch(
            "routes.widget_compint.sb_execute",
            return_value=mock_result,
        ) as _mock_execute,
        patch("routes.widget_compint._check_rate_limit") as _mock_rl,
        patch("routes.widget_compint._get_cached", return_value=None),
        patch("routes.widget_compint._set_cached"),
    ):
        yield _mock_supabase, _mock_execute, _mock_rl


@pytest.fixture
def mock_rpc_uf():
    """Mock RPC with UF=SP data."""
    data = dict(SAMPLE_RPC_DATA)
    data["uf"] = "SP"
    mock_sb = MagicMock()
    mock_result = MagicMock()
    mock_result.data = data
    mock_sb.rpc.return_value = mock_result

    with (
        patch("routes.widget_compint.get_supabase", return_value=mock_sb),
        patch("routes.widget_compint.sb_execute", return_value=mock_result),
        patch("routes.widget_compint._check_rate_limit"),
        patch("routes.widget_compint._get_cached", return_value=None),
        patch("routes.widget_compint._set_cached"),
    ):
        yield


@pytest.fixture
def mock_rpc_empty():
    """Mock RPC returning empty data."""
    empty = {
        "sector": "vigilancia",
        "uf": None,
        "window_months": 12,
        "total_contracts": 0,
        "total_value": 0,
        "top_fornecedores": [],
        "serie_temporal": [],
        "top_orgaos": [],
    }
    mock_sb = MagicMock()
    mock_result = MagicMock()
    mock_result.data = empty
    mock_sb.rpc.return_value = mock_result

    with (
        patch("routes.widget_compint.get_supabase", return_value=mock_sb),
        patch("routes.widget_compint.sb_execute", return_value=mock_result),
        patch("routes.widget_compint._check_rate_limit"),
        patch("routes.widget_compint._get_cached", return_value=None),
        patch("routes.widget_compint._set_cached"),
    ):
        yield


# ============================================================================
# Tests
# ============================================================================


@pytest.mark.asyncio
async def test_market_share_theme(clear_cache, mock_rpc):
    """Test market-share theme returns valid data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/widget/competitive-intel?setor=informatica&tema=market-share")

    assert resp.status_code == 200
    data = resp.json()
    assert data["tema"] == "market-share"
    assert data["setor"] is not None
    assert "dados" in data
    dados = data["dados"]
    assert dados["valor_total"] == 50000000.0
    assert dados["total_contratos"] == 500
    assert len(dados["top_fornecedores"]) == 3
    assert dados["concentracao"] in ("Baixa", "Média", "Alta")
    # Check first supplier has percentage
    assert dados["top_fornecedores"][0]["percentual"] > 0
    assert dados["top_fornecedores"][0]["nome"] == "Tech Solutions Ltda"


@pytest.mark.asyncio
async def test_top_winners_theme(clear_cache, mock_rpc):
    """Test top-winners theme returns valid data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/widget/competitive-intel?setor=informatica&tema=top-winners")

    assert resp.status_code == 200
    data = resp.json()
    assert data["tema"] == "top-winners"
    assert "dados" in data
    winners = data["dados"]["winners"]
    assert len(winners) == 3
    assert winners[0]["nome"] == "Tech Solutions Ltda"
    assert winners[0]["contratos"] == 45
    assert winners[0]["valor_total"] == 15000000.0


@pytest.mark.asyncio
async def test_monthly_trend_theme(clear_cache, mock_rpc):
    """Test monthly-trend theme returns valid data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/widget/competitive-intel?setor=informatica&tema=monthly-trend")

    assert resp.status_code == 200
    data = resp.json()
    assert data["tema"] == "monthly-trend"
    assert "dados" in data
    serie = data["dados"]["serie"]
    assert len(serie) == 12
    assert serie[0]["mes"] == "2025-07"
    assert serie[0]["valor"] == 4000000.0
    assert data["dados"]["tendencia"] in ("crescimento", "estavel", "queda")


@pytest.mark.asyncio
async def test_orgao_ranking_theme(clear_cache, mock_rpc):
    """Test orgao-ranking theme returns valid data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/widget/competitive-intel?setor=informatica&tema=orgao-ranking")

    assert resp.status_code == 200
    data = resp.json()
    assert data["tema"] == "orgao-ranking"
    assert "dados" in data
    orgaos = data["dados"]["orgaos"]
    assert len(orgaos) == 2
    assert orgaos[0]["nome"] == "Secretaria de Tecnologia"
    assert orgaos[0]["valor"] == 8000000.0


@pytest.mark.asyncio
async def test_with_uf_param(clear_cache, mock_rpc_uf):
    """Test with UF parameter."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/v1/widget/competitive-intel?setor=informatica&tema=market-share&uf=SP"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["uf"] == "SP"


@pytest.mark.asyncio
async def test_missing_setor_returns_400(clear_cache):
    """Test missing setor parameter returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/widget/competitive-intel?tema=market-share")

    assert resp.status_code == 422  # FastAPI validates required params (Pydantic)


@pytest.mark.asyncio
async def test_missing_tema_returns_400(clear_cache):
    """Test missing tema parameter returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/widget/competitive-intel?setor=informatica")

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_tema_returns_400(clear_cache):
    """Test invalid tema returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/widget/competitive-intel?setor=informatica&tema=invalid")

    assert resp.status_code == 400
    data = resp.json()
    assert "invalid_tema" in data.get("error", "")


@pytest.mark.asyncio
async def test_invalid_setor_returns_400(clear_cache):
    """Test invalid setor returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/v1/widget/competitive-intel?setor=setor_inexistente&tema=market-share"
        )

    assert resp.status_code == 400
    data = resp.json()
    assert "invalid_setor" in data.get("error", "")


@pytest.mark.asyncio
async def test_invalid_uf_returns_400(clear_cache):
    """Test invalid UF returns 400."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/v1/widget/competitive-intel?setor=informatica&tema=market-share&uf=XYZ"
        )

    assert resp.status_code == 400
    data = resp.json()
    assert "invalid_uf" in data.get("error", "")


@pytest.mark.asyncio
async def test_cors_headers_present(clear_cache, mock_rpc):
    """Test CORS headers are present in response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/widget/competitive-intel?setor=informatica&tema=market-share")

    assert resp.headers.get("access-control-allow-origin") == "*"
    assert resp.headers.get("access-control-allow-methods") is not None
    assert resp.headers.get("cache-control") is not None


@pytest.mark.asyncio
async def test_cors_preflight(clear_cache):
    """Test OPTIONS preflight returns CORS headers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.options("/v1/widget/competitive-intel")

    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "*"
    assert resp.headers.get("access-control-allow-methods") is not None
    assert resp.headers.get("access-control-max-age") is not None


@pytest.mark.asyncio
async def test_cache_control_header(clear_cache, mock_rpc):
    """Test Cache-Control header includes public and max-age."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/v1/widget/competitive-intel?setor=informatica&tema=market-share")

    cc = resp.headers.get("cache-control", "")
    assert "public" in cc
    assert "max-age=" in cc


@pytest.mark.asyncio
async def test_empty_data_returns_valid(clear_cache, mock_rpc_empty):
    """Test empty data still returns a valid response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/v1/widget/competitive-intel?setor=vigilancia&tema=market-share"
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["dados"]["total_contratos"] == 0
    assert data["dados"]["top_fornecedores"] == []


@pytest.mark.asyncio
async def test_rate_limit_applied(clear_cache):
    """Test rate limit blocks excessive requests."""
    from fastapi import HTTPException

    async def _mock_rate_limit_block(*args, **kwargs):
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "retry_after_sec": 60},
        )

    with (
        patch("routes.widget_compint._check_rate_limit", side_effect=_mock_rate_limit_block),
        patch("routes.widget_compint._get_cached", return_value=None),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/v1/widget/competitive-intel?setor=informatica&tema=market-share"
            )

    assert resp.status_code == 429
    data = resp.json()
    # FastAPI wraps HTTPException.detail inside {"detail": ...}
    detail = data.get("detail", {})
    assert "rate_limit_exceeded" in detail.get("error", "")
