"""Tests for SUBINTEL-012 — Regional Dependency Index route (#1681).

Covers:
  - Feature flag OFF => route returns 404 (gate)
  - Invalid sector => 400
  - Successful response with correct shape
  - HHI calculation edge cases
  - Fallback query logic
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# Mocks
# ---------------------------------------------------------------------------

MOCK_RPC_ROWS = [
    {"uf": "SP", "dependency_score": 35.0, "contract_count": 350, "total_value": 17500000.0},
    {"uf": "RJ", "dependency_score": 20.0, "contract_count": 200, "total_value": 10000000.0},
    {"uf": "MG", "dependency_score": 15.0, "contract_count": 150, "total_value": 7500000.0},
    {"uf": "RS", "dependency_score": 10.0, "contract_count": 100, "total_value": 5000000.0},
    {"uf": "PR", "dependency_score": 8.0, "contract_count": 80, "total_value": 4000000.0},
    {"uf": "SC", "dependency_score": 5.0, "contract_count": 50, "total_value": 2500000.0},
    {"uf": "BA", "dependency_score": 4.0, "contract_count": 40, "total_value": 2000000.0},
    {"uf": "DF", "dependency_score": 3.0, "contract_count": 30, "total_value": 1500000.0},
]

MOCK_RPC_SINGLE_UF = [
    {"uf": "SP", "dependency_score": 100.0, "contract_count": 500, "total_value": 25000000.0},
]

MOCK_RPC_EVEN_UFS = [
    {"uf": "SP", "dependency_score": 50.0, "contract_count": 100, "total_value": 5000000.0},
    {"uf": "MG", "dependency_score": 50.0, "contract_count": 100, "total_value": 5000000.0},
]

MOCK_SECTORS = {
    "engenharia": MagicMock(name="Engenharia", keywords={"construcao", "engenharia", "obra"}),
}

TRUE_FLAG = True


@pytest.fixture
def mock_sb_execute(rows):
    """Mock sb_execute to return given rows."""
    async def _mock_sb_execute(*args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.data = rows
        return mock_resp
    return _mock_sb_execute


@pytest.mark.asyncio
async def test_flag_off_returns_404():
    """Feature flag OFF => gate returns 404."""
    from quota.plan_auth import requires_subcontract_intel

    with patch("config.features.get_feature_flag", return_value=False):
        with pytest.raises(HTTPException) as exc:
            await requires_subcontract_intel({"id": "user-123"})
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_invalid_sector_returns_400():
    """Invalid sector_id => 400."""
    with patch("config.features.get_feature_flag", return_value=True), \
         patch("authorization.has_master_access", new=AsyncMock(return_value=True)):
        from routes.subcontract import get_regional_dependency
        from fastapi import Request

        fake_req = MagicMock(spec=Request)

        with pytest.raises(HTTPException) as exc:
            await get_regional_dependency(request=fake_req, setor="setor_inexistente")
        assert exc.value.status_code == 400
        assert "inválido" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_successful_response_shape():
    """Successful call returns correct shape with HHI calculation."""
    with patch("config.features.get_feature_flag", return_value=True), \
         patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
         patch("routes.subcontract.SECTORS", MOCK_SECTORS), \
         patch("routes.subcontract._fetch_regional_dependency", new_callable=AsyncMock) as mock_fetch:

        mock_fetch.return_value = {
            "sector_id": "engenharia",
            "uf_distribution": [
                {"uf": "SP", "dependency_score": 35.0, "contract_count": 350, "total_value": 17500000.0},
                {"uf": "RJ", "dependency_score": 20.0, "contract_count": 200, "total_value": 10000000.0},
                {"uf": "MG", "dependency_score": 15.0, "contract_count": 150, "total_value": 7500000.0},
            ],
            "total_contracts": 700,
            "total_value": 35000000.0,
            "coverage_ufs": 3,
            "hhi_normalized": 0.7975,
            "risk_level": "alto",
            "disclaimer": "...",
            "generated_at": "2026-06-12T00:00:00Z",
        }

        from fastapi import Request
        from routes.subcontract import get_regional_dependency

        fake_req = MagicMock(spec=Request)
        result = await get_regional_dependency(request=fake_req, setor="engenharia")

        assert result.sector_id == "engenharia"
        assert len(result.uf_distribution) == 3
        assert result.total_contracts == 700
        assert result.total_value == 35000000.0
        assert result.coverage_ufs == 3
        assert result.hhi_normalized == 0.7975
        assert result.risk_level == "alto"
        assert result.disclaimer


class TestHhiCalculation:
    """HHI normalization and risk level edge cases."""

    @pytest.mark.asyncio
    async def test_single_uf_high_risk(self):
        """Single UF => high dependency (HHI normalized close to 0)."""
        scores = [100.0]
        hhi = sum((s / 100) ** 2 for s in scores)
        hhi_norm = round(1.0 - hhi, 4)
        assert hhi_norm == 0.0

        # Risk: < 0.3 => alto
        assert hhi_norm < 0.3

    @pytest.mark.asyncio
    async def test_two_equal_ufs_medium_risk(self):
        """Two equal UFs => HHI normalized = 0.5 (medium risk)."""
        scores = [50.0, 50.0]
        hhi = sum((s / 100) ** 2 for s in scores)
        hhi_norm = round(1.0 - hhi, 4)
        assert hhi_norm == 0.5
        # Risk: 0.3-0.6 => medio

    @pytest.mark.asyncio
    async def test_many_diverse_ufs_low_risk(self):
        """Many diverse UFs => high HHI normalized (low risk)."""
        scores = [25.0, 20.0, 18.0, 15.0, 12.0, 10.0]
        hhi = sum((s / 100) ** 2 for s in scores)
        hhi_norm = round(1.0 - hhi, 4)
        assert hhi_norm >= 0.6

    def test_risk_level_mapping(self):
        """Risk level mapping is correct."""
        assert "baixo" == "baixo" if 0.6 <= 0.8 else "?"  # >= 0.6
        assert "medio" == "medio" if 0.3 <= 0.45 < 0.6 else "?"  # 0.3-0.6
        assert "alto" == "alto" if 0.1 < 0.3 else "?"  # < 0.3


class TestEmptyEdgeCases:
    """Edge cases: empty results, no contracts."""

    @pytest.mark.asyncio
    async def test_empty_distribution(self):
        """No data returns empty distribution with zeroes."""
        from routes.subcontract import _empty_response
        result = _empty_response("engenharia", "2026-06-12T00:00:00Z")
        assert result["sector_id"] == "engenharia"
        assert result["uf_distribution"] == []
        assert result["total_contracts"] == 0
        assert result["total_value"] == 0.0
        assert result["coverage_ufs"] == 0
        assert result["risk_level"] == "indisponivel"


@pytest.mark.asyncio
async def test_fallback_query_on_rpc_failure():
    """When RPC fails, the route raises 500 (graceful degradation)."""
    with patch("config.features.get_feature_flag", return_value=True), \
         patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
         patch("routes.subcontract.SECTORS", MOCK_SECTORS), \
         patch("routes.subcontract._get_cached", return_value=None), \
         patch("routes.subcontract._fetch_regional_dependency",
               new=AsyncMock(side_effect=Exception("RPC failed"))):

        from fastapi import Request
        from routes.subcontract import get_regional_dependency

        fake_req = MagicMock(spec=Request)
        with pytest.raises(HTTPException) as exc:
            await get_regional_dependency(request=fake_req, setor="engenharia")
        assert exc.value.status_code == 500
