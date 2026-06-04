"""
C-02 AC3: Tests for confidence field mapping.

Tests that relevance_source is correctly mapped to confidence level:
- keyword -> high
- llm_standard -> medium
- llm_conservative -> low
- llm_zero_match -> low
- None -> None (backward compat)
"""

from pipeline.helpers import _map_confidence


class TestMapConfidence:
    """C-02 AC3: Unit tests for _map_confidence()."""

    def test_keyword_maps_to_high(self):
        """AC3.1: keyword -> high."""
        assert _map_confidence("keyword") == "high"

    def test_llm_standard_maps_to_medium(self):
        """AC3.2: llm_standard -> medium."""
        assert _map_confidence("llm_standard") == "medium"

    def test_llm_conservative_maps_to_low(self):
        """AC3.3: llm_conservative -> low."""
        assert _map_confidence("llm_conservative") == "low"

    def test_llm_zero_match_maps_to_low(self):
        """AC3.4: llm_zero_match -> low."""
        assert _map_confidence("llm_zero_match") == "low"

    def test_none_maps_to_none(self):
        """AC3.5: None -> None (backward compat)."""
        assert _map_confidence(None) is None

    def test_empty_string_maps_to_none(self):
        """Empty string should map to None."""
        assert _map_confidence("") is None

    def test_unknown_source_maps_to_none(self):
        """Unknown relevance source should map to None."""
        assert _map_confidence("unknown_source") is None


class TestConfidenceInLicitacaoItem:
    """C-02 AC1: Test that confidence field exists in schema."""

    def test_confidence_field_exists(self):
        """AC1.1: LicitacaoItem includes confidence field."""
        from schemas import LicitacaoItem
        fields = LicitacaoItem.model_fields
        assert "confidence" in fields

    def test_confidence_is_optional(self):
        """AC1.2: confidence is Optional for backward compatibility."""
        from schemas import LicitacaoItem
        item = LicitacaoItem(
            pncp_id="test-123",
            objeto="Test object",
            orgao="Test org",
            uf="SP",
            valor=100000.0,
            link="https://pncp.gov.br/test",
        )
        assert item.confidence is None

    def test_confidence_accepts_valid_values(self):
        """AC1.3: confidence accepts high, medium, low."""
        from schemas import LicitacaoItem
        for level in ["high", "medium", "low"]:
            item = LicitacaoItem(
                pncp_id="test-123",
                objeto="Test object",
                orgao="Test org",
                uf="SP",
                valor=100000.0,
                link="https://pncp.gov.br/test",
                confidence=level,
            )
            assert item.confidence == level


class TestConfidenceOrdenacao:
    """C-02 AC8: Test confidence sorting in ordenacao."""

    def test_confianca_sort_orders_highest_score_first(self):
        """#1430: Sort by confidence*0.6 + viability*0.4 combined score."""
        from utils.ordenacao import ordenar_licitacoes

        licitacoes = [
            {"objetoCompra": "C", "_confidence_score": 60, "valorTotalEstimado": 100000},
            {"objetoCompra": "A", "_confidence_score": 95, "valorTotalEstimado": 50000},
            {"objetoCompra": "B", "_confidence_score": 75, "valorTotalEstimado": 200000},
        ]
        result = ordenar_licitacoes(licitacoes, "confianca")
        # A: 95*0.6=57, B: 75*0.6=45, C: 60*0.6=36
        assert result[0]["objetoCompra"] == "A"
        assert result[1]["objetoCompra"] == "B"
        assert result[2]["objetoCompra"] == "C"

    def test_confianca_sort_null_last(self):
        """#1430: Results without scores go last."""
        from utils.ordenacao import ordenar_licitacoes

        licitacoes = [
            {"objetoCompra": "Legacy", "valorTotalEstimado": 100000},
            {"objetoCompra": "High", "_confidence_score": 95, "valorTotalEstimado": 50000},
        ]
        result = ordenar_licitacoes(licitacoes, "confianca")
        assert result[0]["objetoCompra"] == "High"
        assert result[1]["objetoCompra"] == "Legacy"

    def test_confianca_sort_within_same_score_by_value(self):
        """#1430: Same combined score sorts by value descending."""
        from utils.ordenacao import ordenar_licitacoes

        licitacoes = [
            {"objetoCompra": "Small", "_confidence_score": 95, "valorTotalEstimado": 50000},
            {"objetoCompra": "Big", "_confidence_score": 95, "valorTotalEstimado": 500000},
        ]
        result = ordenar_licitacoes(licitacoes, "confianca")
        # Same combined = 57, tiebreaker by value descending
        assert result[0]["objetoCompra"] == "Big"
        assert result[1]["objetoCompra"] == "Small"

    def test_confianca_sort_with_viability(self):
        """#1430: Viability score contributes to combined score."""
        from utils.ordenacao import ordenar_licitacoes

        licitacoes = [
            {"objetoCompra": "LowConfHighViab", "_confidence_score": 30, "_viability_score": 90, "valorTotalEstimado": 100000},
            {"objetoCompra": "HighConfLowViab", "_confidence_score": 90, "_viability_score": 30, "valorTotalEstimado": 50000},
        ]
        result = ordenar_licitacoes(licitacoes, "confianca")
        # LowConfHighViab: 30*0.6 + 90*0.4 = 18 + 36 = 54
        # HighConfLowViab: 90*0.6 + 30*0.4 = 54 + 12 = 66
        assert result[0]["objetoCompra"] == "HighConfLowViab"

    def test_confianca_is_valid_ordenacao_option(self):
        """confianca is accepted by BuscaRequest schema."""
        from schemas import BuscaRequest
        req = BuscaRequest(
            ufs=["SP"],
            data_inicial="2026-01-01",
            data_final="2026-01-10",
            ordenacao="confianca",
        )
        assert req.ordenacao == "confianca"
