"""Tests for COMPINT-010: Competitive Territory endpoints.

Covers:
  - GET /v1/intel-concorrente/landscape
  - GET /v1/intel-concorrente/territory/{cnpj}
  - Input validation
  - Auth gate
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from config.features import COMPETITIVE_INTEL_ENABLED
from quota.plan_auth import requires_competitive_intel


@pytest.fixture
def mock_sectors():
    """Patch SECTORS with a valid mock sector entry."""
    mock_sector = SimpleNamespace(name="Hardware e Equipamentos de TI", keywords=["ti", "informatica"])
    with patch("routes.competitive_intel.SECTORS", {"informatica": mock_sector}):
        yield


@pytest.mark.asyncio
class TestCompetitiveLandscape:
    """GET /v1/intel-concorrente/landscape tests."""

    async def test_invalid_sector_returns_400(self):
        """Invalid sector should return HTTP 400."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)):
            with pytest.raises(HTTPException) as exc:
                from routes.competitive_intel import get_competitive_landscape
                await get_competitive_landscape(setor="invalid_sector", uf=None)
        assert exc.value.status_code == 400

    async def test_invalid_uf_returns_400(self, mock_sectors):
        """Invalid UF should return HTTP 400."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)):
            with pytest.raises(HTTPException) as exc:
                from routes.competitive_intel import get_competitive_landscape
                await get_competitive_landscape(setor="informatica", uf="XYZ")
        assert exc.value.status_code == 400

    async def test_returns_valid_response_structure(self, mock_sectors):
        """Valid request should return expected response shape."""
        mock_data = {
            "setor_id": "informatica",
            "setor_nome": "TI",
            "uf": None,
            "total_contratado": 1000000.0,
            "total_contratos": 50,
            "total_concorrentes": 5,
            "top_concorrentes": [],
            "periodo": "Ultimos 12 meses",
            "gerado_em": "2026-06-12T00:00:00",
        }

        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
             patch("routes.competitive_intel._fetch_landscape", new=AsyncMock(return_value=MagicMock(**mock_data))):
            from routes.competitive_intel import get_competitive_landscape
            with patch("routes.competitive_intel._get_cached", return_value=None), \
                 patch("routes.competitive_intel._set_cached"):
                result = await get_competitive_landscape(setor="informatica", uf=None)
        assert result.setor_id == "informatica"
        assert result.total_contratado >= 0


@pytest.mark.asyncio
class TestCompetitiveTerritory:
    """GET /v1/intel-concorrente/territory/{cnpj} tests."""

    async def test_returns_territory_for_valid_cnpj(self):
        """Should return TerritoryData for a valid CNPJ."""
        mock_ufs = [{"uf": "SP", "total_contratado": 500000.0, "numero_contratos": 10, "market_share": 50.0}]
        mock_data = {
            "cnpj": "12345678000195",
            "razao_social": "Empresa Teste Ltda",
            "total_contratado": 1000000.0,
            "total_contratos": 20,
            "ufs": mock_ufs,
        }

        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
             patch("routes.competitive_intel._fetch_territory", new=AsyncMock(return_value=MagicMock(**mock_data))):
            from routes.competitive_intel import get_competitor_territory
            with patch("routes.competitive_intel._get_cached", return_value=None), \
                 patch("routes.competitive_intel._set_cached"):
                result = await get_competitor_territory(cnpj="12345678000195")
        assert result.cnpj == "12345678000195"
        assert result.total_contratado == 1000000.0

    async def test_returns_empty_for_unknown_cnpj(self):
        """Unknown CNPJ should return zeroed data."""
        mock_data = {
            "cnpj": "00000000000000",
            "razao_social": "Fornecedor nao encontrado",
            "total_contratado": 0,
            "total_contratos": 0,
            "ufs": [],
        }

        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
             patch("routes.competitive_intel._fetch_territory", new=AsyncMock(return_value=MagicMock(**mock_data))):
            from routes.competitive_intel import get_competitor_territory
            with patch("routes.competitive_intel._get_cached", return_value=None), \
                 patch("routes.competitive_intel._set_cached"):
                result = await get_competitor_territory(cnpj="00000000000000")
        assert result.total_contratado == 0
        assert len(result.ufs) == 0


class TestGateIntegration:
    """Verify the gating dependency works correctly."""

    def test_competitive_intel_flag_default_true(self):
        """COMPETITIVE_INTEL_ENABLED must default to True so dev works."""
        assert COMPETITIVE_INTEL_ENABLED is True

    @pytest.mark.asyncio
    async def test_gate_requires_auth(self):
        """Gate should raise when called without proper auth."""
        with patch("config.features.get_feature_flag", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await requires_competitive_intel({"id": "user-123"})
            assert exc.value.status_code == 404
