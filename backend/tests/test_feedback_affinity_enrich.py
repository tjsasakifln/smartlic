"""FEEDBACK-003: Tests for user-sector affinity factor in enrichment pipeline.

Covers:
- Affinity factor formula: min(1.0, 0.5 + affinity)
- Affinity applied in viability path (combined_score)
- Affinity applied in simplified/fallback path (boosted_conf)
- Neutral fallback on DB failure / timeout
- Neutral default when user/sector missing
- _run_with_budget wrapping
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from search_context import SearchContext
from search_pipeline import SearchPipeline


# ── helpers ────────────────────────────────────────────────────────────────


def _make_bid(objeto: str, conf: float = 50, viab: float | None = None,
              valor: float = 100_000, relevance_source: str | None = None,
              term_density: float = 0.0) -> dict:
    """Create a minimal bid dict for enrichment testing."""
    bid: dict = {
        "objetoCompra": objeto,
        "_confidence_score": conf,
        "valorTotalEstimado": valor,
    }
    if viab is not None:
        bid["_viability_score"] = viab
    if relevance_source:
        bid["_relevance_source"] = relevance_source
    if term_density:
        bid["_term_density"] = term_density
    return bid


def _make_ctx(*, user: dict | None = None, sector=None, licitacoes=None,
              custom_terms=None, ordenacao: str = "data_desc",
              active_keywords: set | None = None,
              is_simplified: bool = True) -> SearchContext:
    """Create a minimal SearchContext.

    Defaults is_simplified=True to skip viability assessment (not under test).
    """
    from datetime import datetime, timezone

    if active_keywords is None:
        active_keywords = set()

    ctx = SearchContext(
        user=user,
        sector=sector,
        licitacoes_filtradas=licitacoes or [],
        custom_terms=custom_terms or [],
        active_keywords=active_keywords,
        request=MagicMock(
            data_inicial=datetime(2026, 1, 1, tzinfo=timezone.utc),
            data_final=datetime(2026, 1, 10, tzinfo=timezone.utc),
            ufs=["SP"],
            modalidades=[],
            ordenacao=ordenacao,
            search_id="test-search-id",
        ),
        is_simplified=is_simplified,
        user_profile=None,
    )
    return ctx


def _make_deps():
    """Create minimal pipeline dependencies."""
    return {}


# ── Formula correctness ─────────────────────────────────────────────────────


class TestAffinityFactorFormula:
    """FEEDBACK-003 AC1: affinity_factor = min(1.0, 0.5 + affinity)."""

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    @patch("pipeline.stages.enrich.count_phrase_matches", return_value=0)
    @patch("pipeline.stages.enrich.score_relevance", return_value=0.0)
    async def test_cold_start_neutral(
        self, mock_score, mock_count, mock_ordenar
    ):
        """affinity=0.5 → factor=min(1.0, 1.0)=1.0 (neutral, no change)."""
        with patch(
            "pipeline.stages.enrich._run_with_budget",
            new_callable=AsyncMock,
        ) as mock_budget:
            mock_budget.return_value = 0.5  # cold start
            mock_ordenar.return_value = []

            bids = [_make_bid("Item A", conf=80, viab=80)]
            ctx = _make_ctx(
                user={"id": "user-123"},
                sector=MagicMock(id="sector-99"),
                licitacoes=bids,
                is_simplified=True,  # Skip viability assessment
            )
            pipeline = SearchPipeline(_make_deps())
            await pipeline.stage_enrich(ctx)

            assert bids[0]["_affinity_factor"] == 1.0
            # combined_score unchanged (no relevance_boost)
            expected = round(80 * 0.6 + 80 * 0.4)
            assert bids[0]["_combined_score"] == expected

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    @patch("pipeline.stages.enrich.count_phrase_matches", return_value=0)
    @patch("pipeline.stages.enrich.score_relevance", return_value=0.0)
    async def test_low_affinity_reduces_score(
        self, mock_score, mock_count, mock_ordenar
    ):
        """affinity=0.0 → factor=min(1.0, 0.5)=0.5 (50% reduction)."""
        with patch(
            "pipeline.stages.enrich._run_with_budget",
            new_callable=AsyncMock,
        ) as mock_budget:
            mock_budget.return_value = 0.0
            mock_ordenar.return_value = []

            bids = [_make_bid("Item A", conf=80, viab=80)]
            ctx = _make_ctx(
                user={"id": "user-123"},
                sector=MagicMock(id="sector-99"),
                licitacoes=bids,
            )
            pipeline = SearchPipeline(_make_deps())
            await pipeline.stage_enrich(ctx)

            assert bids[0]["_affinity_factor"] == 0.5
            base = 80 * 0.6 + 80 * 0.4  # 80
            assert bids[0]["_combined_score"] == round(base * 0.5)  # 40

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    @patch("pipeline.stages.enrich.count_phrase_matches", return_value=0)
    @patch("pipeline.stages.enrich.score_relevance", return_value=0.0)
    async def test_high_affinity_capped_at_one(
        self, mock_score, mock_count, mock_ordenar
    ):
        """affinity=1.0 → factor=min(1.0, 1.5)=1.0 (capped, no boost)."""
        with patch(
            "pipeline.stages.enrich._run_with_budget",
            new_callable=AsyncMock,
        ) as mock_budget:
            mock_budget.return_value = 1.0
            mock_ordenar.return_value = []

            bids = [_make_bid("Item A", conf=80, viab=80)]
            ctx = _make_ctx(
                user={"id": "user-123"},
                sector=MagicMock(id="sector-99"),
                licitacoes=bids,
            )
            pipeline = SearchPipeline(_make_deps())
            await pipeline.stage_enrich(ctx)

            assert bids[0]["_affinity_factor"] == 1.0
            base = 80 * 0.6 + 80 * 0.4
            assert bids[0]["_combined_score"] == round(base)  # unchanged


# ── Simplified / fallback path ───────────────────────────────────────────────


class TestAffinityFactorFallbackPath:
    """FEEDBACK-003: Affinity applied in simplified search path too."""

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    @patch("pipeline.stages.enrich.count_phrase_matches", return_value=0)
    @patch("pipeline.stages.enrich.score_relevance", return_value=0.0)
    async def test_affinity_applied_in_fallback(
        self, mock_score, mock_count, mock_ordenar
    ):
        """Simplified search (no viability scores) still gets affinity applied."""
        with patch(
            "pipeline.stages.enrich._run_with_budget",
            new_callable=AsyncMock,
        ) as mock_budget:
            mock_budget.return_value = 0.0  # factor=0.5
            mock_ordenar.return_value = []

            # No _viability_score → viability_active=False → fallback path
            bids = [_make_bid("Item A", conf=80)]
            ctx = _make_ctx(
                user={"id": "user-123"},
                sector=MagicMock(id="sector-99"),
                licitacoes=bids,
            )
            pipeline = SearchPipeline(_make_deps())
            await pipeline.stage_enrich(ctx)

            assert bids[0]["_affinity_factor"] == 0.5
            # boosted_conf = (80 + 0) * 0.5 = 40 → band 2
            # sorting key: (2, -40, -100000) — low conf band

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    @patch("pipeline.stages.enrich.count_phrase_matches", return_value=0)
    @patch("pipeline.stages.enrich.score_relevance", return_value=0.0)
    async def test_fallback_neutral_when_no_user(
        self, mock_score, mock_count, mock_ordenar
    ):
        """Without user, fallback path uses neutral factor=1.0."""
        mock_ordenar.return_value = []

        bids = [_make_bid("Item A", conf=80)]
        ctx = _make_ctx(
            user=None,  # no user
            sector=MagicMock(id="sector-99"),
            licitacoes=bids,
        )
        pipeline = SearchPipeline(_make_deps())
        await pipeline.stage_enrich(ctx)

        assert bids[0]["_affinity_factor"] == 1.0


# ── Error resilience ─────────────────────────────────────────────────────────


class TestAffinityFactorErrorHandling:
    """FEEDBACK-003: Affinity lookup failures gracefully fall back to neutral."""

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    @patch("pipeline.stages.enrich.count_phrase_matches", return_value=0)
    @patch("pipeline.stages.enrich.score_relevance", return_value=0.0)
    async def test_db_failure_falls_back_to_neutral(
        self, mock_score, mock_count, mock_ordenar
    ):
        """When get_affinity raises, factor stays 1.0."""
        with patch(
            "pipeline.stages.enrich._run_with_budget",
            new_callable=AsyncMock,
        ) as mock_budget:
            mock_budget.side_effect = RuntimeError("DB connection refused")
            mock_ordenar.return_value = []

            bids = [_make_bid("Item A", conf=80, viab=80)]
            ctx = _make_ctx(
                user={"id": "user-123"},
                sector=MagicMock(id="sector-99"),
                licitacoes=bids,
            )
            pipeline = SearchPipeline(_make_deps())
            await pipeline.stage_enrich(ctx)

            assert bids[0]["_affinity_factor"] == 1.0
            base = 80 * 0.6 + 80 * 0.4
            assert bids[0]["_combined_score"] == round(base)

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    @patch("pipeline.stages.enrich.count_phrase_matches", return_value=0)
    @patch("pipeline.stages.enrich.score_relevance", return_value=0.0)
    async def test_timeout_falls_back_to_neutral(
        self, mock_score, mock_count, mock_ordenar
    ):
        """When _run_with_budget times out, factor stays 1.0."""
        import asyncio

        with patch(
            "pipeline.stages.enrich._run_with_budget",
            new_callable=AsyncMock,
        ) as mock_budget:
            mock_budget.side_effect = asyncio.TimeoutError("budget exceeded")
            mock_ordenar.return_value = []

            bids = [_make_bid("Item A", conf=80, viab=80)]
            ctx = _make_ctx(
                user={"id": "user-123"},
                sector=MagicMock(id="sector-99"),
                licitacoes=bids,
            )
            pipeline = SearchPipeline(_make_deps())
            await pipeline.stage_enrich(ctx)

            assert bids[0]["_affinity_factor"] == 1.0

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    async def test_no_user_no_fetch(self, mock_ordenar):
        """When user is None, get_affinity is never called."""
        mock_ordenar.return_value = []

        bids = [_make_bid("Item A", conf=80)]
        ctx = _make_ctx(
            user=None,
            sector=MagicMock(id="sector-99"),
            licitacoes=bids,
        )
        pipeline = SearchPipeline(_make_deps())
        await pipeline.stage_enrich(ctx)

        # _run_with_budget not patched → if it were called it would fail
        assert bids[0].get("_affinity_factor", 1.0) == 1.0

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    async def test_no_licitacoes_no_fetch(self, mock_ordenar):
        """When licitacoes_filtradas is empty, get_affinity is never called."""
        mock_ordenar.return_value = []

        ctx = _make_ctx(
            user={"id": "user-123"},
            sector=MagicMock(id="sector-99"),
            licitacoes=[],
        )
        pipeline = SearchPipeline(_make_deps())
        await pipeline.stage_enrich(ctx)

        # No bids → no _affinity_factor set anywhere, no fetch attempted


# ── Budget wrapping ──────────────────────────────────────────────────────────


class TestAffinityFactorBudget:
    """FEEDBACK-003 + STORY-4.4: Affinity fetch uses _run_with_budget."""

    @pytest.mark.asyncio
    @patch("pipeline.stages.enrich.ordenar_licitacoes")
    async def test_budget_phase_label(self, mock_ordenar):
        """_run_with_budget called with phase='enrich', source='affinity'."""
        from pipeline.stages.enrich import _AFFINITY_BUDGET_S

        with patch(
            "pipeline.stages.enrich._run_with_budget",
            new_callable=AsyncMock,
        ) as mock_budget:
            mock_budget.return_value = 0.5
            mock_ordenar.return_value = []

            bids = [_make_bid("Item A", conf=80, viab=80)]
            ctx = _make_ctx(
                user={"id": "user-123"},
                sector=MagicMock(id="sector-99"),
                licitacoes=bids,
            )
            pipeline = SearchPipeline(_make_deps())
            await pipeline.stage_enrich(ctx)

            mock_budget.assert_called_once()
            call_kwargs = mock_budget.call_args.kwargs
            assert call_kwargs["budget"] == _AFFINITY_BUDGET_S
            assert call_kwargs["phase"] == "enrich"
            assert call_kwargs["source"] == "affinity"
