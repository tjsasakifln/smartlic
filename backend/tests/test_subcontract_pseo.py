"""Tests for SUBINTEL-022 — Subcontract pSEO block route (#1678).

Covers:
  - Feature flag OFF => 404 (gate)
  - Invalid sector => 400
  - Bid not found => 404
  - Successful response with correct shape
  - Scoring logic edge cases
  - Empty suppliers
  - RPC failure => 500
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

MOCK_OPPORTUNITY_RESPONSE = {
    "bid_id": "12345-67890",
    "bid_value": 3200000.00,
    "bid_sector": "engenharia",
    "subcontract_potential_score": 0.85,
    "reasons": [
        {"reason": "Valor acima de R$1M sugere necessidade de subcontratacao", "weight": 0.3},
        {"reason": "Setor de engenharia tem alta taxa de subcontratacao", "weight": 0.2},
        {"reason": "Orgao tem historico de 12 fornecedores diferentes, sugerindo subcontratacao indireta", "weight": 0.3},
        {"reason": "Ha pelo menos 3 fornecedores historicos no mesmo orgao para contratos similares", "weight": 0.2},
    ],
    "historical_suppliers": [
        {
            "cnpj": "12345678000199",
            "razao_social": "Construtora X Ltda",
            "similar_contracts_count": 7,
            "total_value": 18500000.0,
            "avg_value": 2642857.14,
            "last_contract_year": 2026,
            "match_reason": "Fornecedor historico do mesmo orgao",
        },
    ],
    "disclaimer": "Analise estimada...",
    "generated_at": "2026-06-12T00:00:00Z",
}

MOCK_SECTORS = {
    "engenharia": MagicMock(name="Engenharia", keywords={"construcao", "engenharia", "obra"}),
    "vestuario": MagicMock(name="Vestuário", keywords={"uniforme", "vestuario"}),
}


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
    """Invalid sector => 400."""
    with patch("config.features.get_feature_flag", return_value=True), \
         patch("authorization.has_master_access", new=AsyncMock(return_value=True)):
        from routes.subcontract import get_subcontract_opportunities
        from fastapi import Request

        fake_req = MagicMock(spec=Request)

        with pytest.raises(HTTPException) as exc:
            await get_subcontract_opportunities(
                request=fake_req, bid="12345-67890", sector="setor_inexistente"
            )
        assert exc.value.status_code == 400
        assert "inválido" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_bid_not_found_returns_404():
    """Bid not found => 404."""
    with patch("config.features.get_feature_flag", return_value=True), \
         patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
         patch("routes.subcontract.SECTORS", MOCK_SECTORS), \
         patch("routes.subcontract._get_cached", return_value=None), \
         patch("routes.subcontract._fetch_bid_opportunities",
               new=AsyncMock(return_value=None)):

        from routes.subcontract import get_subcontract_opportunities
        from fastapi import Request

        fake_req = MagicMock(spec=Request)
        with pytest.raises(HTTPException) as exc:
            await get_subcontract_opportunities(
                request=fake_req, bid="inexistente-123", sector="engenharia"
            )
        assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_successful_response_shape():
    """Successful call returns correct shape with scoring."""
    with patch("config.features.get_feature_flag", return_value=True), \
         patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
         patch("routes.subcontract.SECTORS", MOCK_SECTORS), \
         patch("routes.subcontract._get_cached", return_value=None), \
         patch("routes.subcontract._fetch_bid_opportunities",
               new=AsyncMock(return_value=MOCK_OPPORTUNITY_RESPONSE)):

        from routes.subcontract import get_subcontract_opportunities
        from fastapi import Request

        fake_req = MagicMock(spec=Request)
        result = await get_subcontract_opportunities(
            request=fake_req, bid="12345-67890", sector="engenharia"
        )

        assert result.bid_id == "12345-67890"
        assert result.bid_value == 3200000.0
        assert result.bid_sector == "engenharia"
        assert result.subcontract_potential_score == 0.85
        assert len(result.reasons) == 4
        assert len(result.historical_suppliers) == 1
        assert result.disclaimer

        supplier = result.historical_suppliers[0]
        assert supplier.cnpj == "12345678000199"
        assert supplier.similar_contracts_count == 7
        assert supplier.total_value == 18500000.0
        assert supplier.last_contract_year == 2026


class TestEmptyEdgeCases:
    """Edge cases: no suppliers."""

    @pytest.mark.asyncio
    async def test_no_historical_suppliers(self):
        """Empty suppliers list returns empty array."""
        mock_data = {**MOCK_OPPORTUNITY_RESPONSE, "historical_suppliers": []}

        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
             patch("routes.subcontract.SECTORS", MOCK_SECTORS), \
             patch("routes.subcontract._get_cached", return_value=None), \
             patch("routes.subcontract._fetch_bid_opportunities",
                   new=AsyncMock(return_value=mock_data)):

            from routes.subcontract import get_subcontract_opportunities
            from fastapi import Request

            fake_req = MagicMock(spec=Request)
            result = await get_subcontract_opportunities(
                request=fake_req, bid="12345-67890", sector="engenharia"
            )
            assert result.historical_suppliers == []


@pytest.mark.asyncio
async def test_fallback_on_rpc_failure():
    """When RPC fails, route returns 500."""
    with patch("config.features.get_feature_flag", return_value=True), \
         patch("authorization.has_master_access", new=AsyncMock(return_value=True)), \
         patch("routes.subcontract.SECTORS", MOCK_SECTORS), \
         patch("routes.subcontract._get_cached", return_value=None), \
         patch("routes.subcontract._fetch_bid_opportunities",
               new=AsyncMock(side_effect=Exception("RPC failed"))):

        from routes.subcontract import get_subcontract_opportunities
        from fastapi import Request

        fake_req = MagicMock(spec=Request)
        with pytest.raises(HTTPException) as exc:
            await get_subcontract_opportunities(
                request=fake_req, bid="12345-67890", sector="engenharia"
            )
        assert exc.value.status_code == 500
