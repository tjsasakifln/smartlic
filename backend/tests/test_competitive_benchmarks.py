"""Tests for COMPINT-013: Sector Benchmarks endpoint.

Covers:
  Issue: #1667 COMPINT-013 — Sector Benchmarks
  - GET /v1/intel-concorrente/benchmarks
  - Response validation
  - Invalid input handling
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


@pytest.fixture
def mock_sectors():
    """Patch SECTORS with a valid mock sector entry."""
    mock_sector = SimpleNamespace(name="TI", keywords=["ti", "informatica"])
    with patch("routes.competitive_intel.SECTORS", {"informatica": mock_sector}):
        yield


@pytest.mark.asyncio
class TestCompetitiveBenchmarks:
    """GET /v1/intel-concorrente/benchmarks tests."""

    async def test_invalid_sector_returns_400(self, mock_sectors):
        """Invalid sector should return HTTP 400."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)):
            from routes.competitive_intel import get_competitor_benchmarks
            with pytest.raises(HTTPException) as exc:
                await get_competitor_benchmarks(
                    cnpj="12345678000195", setor="invalid_sector"
                )
        assert exc.value.status_code == 400

    async def test_returns_benchmark_structure(self, mock_sectors):
        """Valid request should return SectorBenchmarkResponse."""
        mock_metricas = [{
            "metrica": "ticket_medio",
            "label": "Ticket Medio",
            "valor_concorrente": 50000.0,
            "percentil_concorrente": 65,
            "benchmark_setor": {"p25": 10000.0, "p50": 30000.0, "p75": 80000.0},
            "descricao": "Test description",
        }]
        mock_data = {
            "cnpj": "12345678000195",
            "razao_social": "Empresa Teste Ltda",
            "setor_id": "informatica",
            "setor_nome": "TI",
            "metricas": mock_metricas,
            "gerado_em": "2026-06-12T00:00:00",
        }

        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
             patch("routes.competitive_intel._fetch_benchmarks",
                   new=AsyncMock(return_value=MagicMock(**mock_data))):
            from routes.competitive_intel import get_competitor_benchmarks
            with patch("routes.competitive_intel._get_cached", return_value=None), \
                 patch("routes.competitive_intel._set_cached"):
                result = await get_competitor_benchmarks(
                    cnpj="12345678000195", setor="informatica"
                )
        assert result.setor_id == "informatica"
        assert len(result.metricas) == 1
        assert result.metricas[0]["metrica"] == "ticket_medio"

    async def test_cache_hit(self, mock_sectors):
        """Cached responses should be returned without querying _fetch_benchmarks."""
        cached_data = {
            "cnpj": "12345678000195",
            "razao_social": "Cached Ltda",
            "setor_id": "informatica",
            "setor_nome": "TI",
            "metricas": [],
            "gerado_em": "2026-06-12T00:00:00",
        }

        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
             patch("routes.competitive_intel._get_cached", return_value=cached_data):
            from routes.competitive_intel import get_competitor_benchmarks
            result = await get_competitor_benchmarks(
                cnpj="12345678000195", setor="informatica"
            )
        # When hitting cache, the response is reconstructed from cached_data dict
        assert result.setor_nome == "TI"
        assert result.razao_social == "Cached Ltda"
