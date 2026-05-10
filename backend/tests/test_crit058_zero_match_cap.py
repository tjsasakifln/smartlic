"""CRIT-058: Cap + Prioritization for Zero-Match LLM Classification.

Tests that the async ``classify_zero_match_job`` ARQ job applies a configurable
cap on the zero-match pool, prioritizes the cap by ``valorTotalEstimado``, and
marks dropped items as ``pending_review`` with reason ``zero_match_cap_exceeded``.

Architecture note (#971 AC3 path b):
The CRIT-058 cap/prioritization logic lives in the ARQ job
(``backend/jobs/queue/jobs.py::classify_zero_match_job``), mirroring the
CRIT-057 budget guard refactor. The synchronous filter
(``backend/filter/pipeline.py``) intentionally does NOT apply the cap — it
enqueues the entire zero-match pool to the job, which then caps + classifies
asynchronously. These tests therefore exercise the job directly, not
``aplicar_todos_filtros``.
"""

import asyncio
from unittest.mock import patch, MagicMock, AsyncMock


def _make_lic(
    objeto: str = "Aquisicao de equipamentos de construcao civil para obras publicas",
    valor: float = 100_000.0,
    idx: int = 0,
) -> dict:
    """Create a minimal licitacao dict eligible for zero-match classification."""
    return {
        "objetoCompra": f"{objeto} item {idx:04d}",
        "valorTotalEstimado": valor,
        "uf": "SP",
        "orgaoEntidade": {"ufSigla": "SP"},
    }


def _run_job(candidates, search_id: str = "crit058-test", capture=None):
    """Run classify_zero_match_job synchronously and capture batch invocations."""
    from jobs.queue.jobs import classify_zero_match_job

    captured_items = capture if capture is not None else []

    def fast_classify_batch(items, setor_name=None, setor_id=None, search_id=None, **kwargs):
        captured_items.extend(items)
        return [{"is_primary": True, "confidence": 65, "evidence": ["match"]}] * len(items)

    async def _noop_store(*args, **kwargs):
        return None

    with patch("llm_arbiter._classify_zero_match_batch", fast_classify_batch), \
         patch("jobs.queue.result_store.store_zero_match_results", side_effect=_noop_store), \
         patch("progress.get_tracker", new_callable=AsyncMock, return_value=None):
        result = asyncio.run(
            classify_zero_match_job(
                ctx={},
                search_id=search_id,
                candidates=candidates,
                setor="engenharia",
                sector_name="Engenharia",
            )
        )

    return result, captured_items


class TestCrit058CapBasic:
    """AC1: Configurable cap on zero-match items."""

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 200)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_pool_500_cap_200_classifies_200(self):
        """500 items, cap=200 → exactly 200 classified, 300 deferred as cap_exceeded."""
        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(500)]

        result, classified = _run_job(licitacoes)

        assert result["status"] == "completed"
        assert result["total_classified"] == 200
        assert len(classified) == 200

        cap_pending = [
            lic for lic in licitacoes
            if lic.get("_pending_review_reason") == "zero_match_cap_exceeded"
        ]
        assert len(cap_pending) == 300, f"Expected 300 cap-deferred, got {len(cap_pending)}"
        # Job result `pending` count includes cap-deferred items.
        assert result["pending"] >= 300

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 9999)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_cap_not_triggered_small_pool(self):
        """50 items, cap=9999 → classifies all, cap NOT activated."""
        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(50)]

        result, classified = _run_job(licitacoes)

        assert result["status"] == "completed"
        assert result["total_classified"] == 50
        assert len(classified) == 50

        cap_pending = [
            lic for lic in licitacoes
            if lic.get("_pending_review_reason") == "zero_match_cap_exceeded"
        ]
        assert len(cap_pending) == 0

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 100)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_cap_equal_to_pool_size(self):
        """cap equals pool size → classifies all, cap NOT activated."""
        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(100)]

        result, classified = _run_job(licitacoes)

        assert result["total_classified"] == 100
        assert len(classified) == 100

        cap_pending = [
            lic for lic in licitacoes
            if lic.get("_pending_review_reason") == "zero_match_cap_exceeded"
        ]
        assert len(cap_pending) == 0


class TestCrit058ValuePrioritization:
    """AC2: Items sorted by value descending before cap."""

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 200)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_top_by_value_classified_first(self):
        """ratio=1.0 + cap=200 → top-200 by value classified, low-value deferred."""
        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(500)]

        result, classified = _run_job(licitacoes)

        classified_objetos = {item["objeto"] for item in classified}
        # Top 200 values are indices 300..499.
        for i in range(300, 500):
            obj_fragment = f"item {i:04d}"
            matching = [o for o in classified_objetos if obj_fragment in o]
            assert len(matching) > 0, f"Expected item {i} (value={i*1000}) to be classified"

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 10)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_no_value_items_go_last(self):
        """Items with None value sort last; high-value items classified first."""
        licitacoes = []
        for i in range(10):
            lic = _make_lic(valor=0, idx=i)
            lic["valorTotalEstimado"] = None
            licitacoes.append(lic)
        for i in range(10, 20):
            licitacoes.append(_make_lic(valor=float(i * 100_000), idx=i))

        result, classified = _run_job(licitacoes)

        classified_objetos = {item["objeto"] for item in classified}
        for i in range(10, 20):
            obj_fragment = f"item {i:04d}"
            matching = [o for o in classified_objetos if obj_fragment in o]
            assert len(matching) > 0, f"High-value item {i} should be classified"


class TestCrit058PendingReview:
    """AC5: Deferred items marked with correct metadata."""

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 10)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_pending_review_fields(self):
        """Deferred items have full pending_review metadata set."""
        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(50)]

        result, classified = _run_job(licitacoes)

        pending = [lic for lic in licitacoes if lic.get("_pending_review")]
        assert len(pending) == 40

        for lic in pending:
            assert lic["_relevance_source"] == "pending_review"
            assert lic["_pending_review"] is True
            assert lic["_pending_review_reason"] == "zero_match_cap_exceeded"
            assert lic["_term_density"] == 0.0
            assert lic["_matched_terms"] == []
            assert lic["_confidence_score"] == 0
            assert lic["_llm_evidence"] == []

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 10)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_cap_exceeded_vs_budget_exceeded_distinguishable(self):
        """CRIT-058 cap_exceeded reason is distinguishable from CRIT-057 budget_exceeded."""
        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(50)]

        result, classified = _run_job(licitacoes)

        cap_pending = [
            lic for lic in licitacoes
            if lic.get("_pending_review_reason") == "zero_match_cap_exceeded"
        ]
        budget_pending = [
            lic for lic in licitacoes
            if lic.get("_pending_review_reason") == "zero_match_budget_exceeded"
        ]

        assert len(cap_pending) == 40
        assert len(budget_pending) == 0


class TestCrit058CompatibilityCrit057:
    """AC8: Cap (CRIT-058) applies BEFORE LLM loop; budget (CRIT-057) applies DURING."""

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 5)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 50)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_cap_reduces_pool_budget_not_needed(self):
        """Cap reduces 200→50, budget 999s sufficient → CRIT-057 does NOT fire."""
        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(200)]

        result, classified = _run_job(licitacoes)

        assert result["total_classified"] == 50

        cap_pending = [
            lic for lic in licitacoes
            if lic.get("_pending_review_reason") == "zero_match_cap_exceeded"
        ]
        assert len(cap_pending) == 150  # 200 - 50

        budget_pending = [
            lic for lic in licitacoes
            if lic.get("_pending_review_reason") == "zero_match_budget_exceeded"
        ]
        assert len(budget_pending) == 0


class TestCrit058ValueStringParsing:
    """Edge cases for value parsing in sorting."""

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 5)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_string_value_with_comma(self):
        """Brazilian format '1.500.000,00' parses correctly for sorting."""
        licitacoes = []
        lic_high = _make_lic(idx=0)
        lic_high["valorTotalEstimado"] = "1.500.000,00"
        licitacoes.append(lic_high)

        lic_low = _make_lic(idx=1)
        lic_low["valorTotalEstimado"] = "10.000,00"
        licitacoes.append(lic_low)

        for i in range(2, 12):
            licitacoes.append(_make_lic(valor=float(i * 100), idx=i))

        result, classified = _run_job(licitacoes)

        classified_objetos = " ".join(item["objeto"] for item in classified)
        assert "item 0000" in classified_objetos, "1.5M item should be classified first"

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 5)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_valor_estimado_fallback(self):
        """Uses valorEstimado when valorTotalEstimado is missing."""
        licitacoes = []
        lic = _make_lic(idx=0)
        del lic["valorTotalEstimado"]
        lic["valorEstimado"] = 999_999.0
        licitacoes.append(lic)

        for i in range(1, 20):
            licitacoes.append(_make_lic(valor=float(i * 10), idx=i))

        result, classified = _run_job(licitacoes)

        classified_objetos = " ".join(item["objeto"] for item in classified)
        assert "item 0000" in classified_objetos


class TestCrit058Metrics:
    """AC4/AC6: Prometheus metrics observed."""

    def test_prometheus_metrics_called_when_cap_applied(self):
        """When pool exceeds cap, ZERO_MATCH_CAP_APPLIED_TOTAL.inc() and POOL_SIZE.observe() are called."""
        from jobs.queue.jobs import classify_zero_match_job

        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(50)]

        def fast_classify_batch(items, setor_name=None, setor_id=None, search_id=None, **kwargs):
            return [{"is_primary": True, "confidence": 65, "evidence": []}] * len(items)

        async def _noop_store(*args, **kwargs):
            return None

        mock_cap_total = MagicMock()
        mock_pool_size = MagicMock()

        with patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 20), \
             patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999), \
             patch("config.LLM_FALLBACK_PENDING_ENABLED", True), \
             patch("config.MAX_ZERO_MATCH_ITEMS", 10), \
             patch("config.ZERO_MATCH_VALUE_RATIO", 1.0), \
             patch("metrics.ZERO_MATCH_CAP_APPLIED_TOTAL", mock_cap_total), \
             patch("metrics.ZERO_MATCH_POOL_SIZE", mock_pool_size), \
             patch("llm_arbiter._classify_zero_match_batch", fast_classify_batch), \
             patch("jobs.queue.result_store.store_zero_match_results", side_effect=_noop_store), \
             patch("progress.get_tracker", new_callable=AsyncMock, return_value=None):
            asyncio.run(
                classify_zero_match_job(
                    ctx={},
                    search_id="crit058-metrics",
                    candidates=licitacoes,
                    setor="engenharia",
                    sector_name="Engenharia",
                )
            )

        mock_cap_total.inc.assert_called_once()
        mock_pool_size.observe.assert_called_once_with(50)

    def test_prometheus_pool_size_observed_below_cap(self):
        """ZERO_MATCH_POOL_SIZE always observed; CAP_APPLIED only when cap fires."""
        from jobs.queue.jobs import classify_zero_match_job

        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(20)]

        def fast_classify_batch(items, setor_name=None, setor_id=None, search_id=None, **kwargs):
            return [{"is_primary": True, "confidence": 65, "evidence": []}] * len(items)

        async def _noop_store(*args, **kwargs):
            return None

        mock_cap_total = MagicMock()
        mock_pool_size = MagicMock()

        with patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 20), \
             patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999), \
             patch("config.LLM_FALLBACK_PENDING_ENABLED", True), \
             patch("config.MAX_ZERO_MATCH_ITEMS", 100), \
             patch("config.ZERO_MATCH_VALUE_RATIO", 1.0), \
             patch("metrics.ZERO_MATCH_CAP_APPLIED_TOTAL", mock_cap_total), \
             patch("metrics.ZERO_MATCH_POOL_SIZE", mock_pool_size), \
             patch("llm_arbiter._classify_zero_match_batch", fast_classify_batch), \
             patch("jobs.queue.result_store.store_zero_match_results", side_effect=_noop_store), \
             patch("progress.get_tracker", new_callable=AsyncMock, return_value=None):
            asyncio.run(
                classify_zero_match_job(
                    ctx={},
                    search_id="crit058-below-cap",
                    candidates=licitacoes,
                    setor="engenharia",
                    sector_name="Engenharia",
                )
            )

        # Cap not triggered.
        mock_cap_total.inc.assert_not_called()
        # Pool size always observed.
        mock_pool_size.observe.assert_called_once_with(20)


class TestCrit058EdgeCases:
    """Edge cases and boundary conditions."""

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 200)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_empty_pool_no_crash(self):
        """Empty pool → no crash, no metrics inc, classifies nothing."""
        result, classified = _run_job([])

        assert result["total_classified"] == 0
        assert len(classified) == 0

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 200)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_single_item_below_cap(self):
        """Single item, cap=200 → classifies the item."""
        licitacoes = [_make_lic(valor=100_000, idx=0)]

        result, classified = _run_job(licitacoes)

        assert result["total_classified"] == 1
        assert len(classified) == 1
        cap_pending = [
            lic for lic in licitacoes
            if lic.get("_pending_review_reason") == "zero_match_cap_exceeded"
        ]
        assert len(cap_pending) == 0

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 30)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_all_items_same_value(self):
        """All items have same value → no crash in sorting."""
        licitacoes = [_make_lic(valor=50_000, idx=i) for i in range(100)]

        result, classified = _run_job(licitacoes)

        assert result["total_classified"] == 30
        assert len(classified) == 30

    @patch("config.LLM_ZERO_MATCH_BATCH_SIZE", 50)
    @patch("config.FILTER_ZERO_MATCH_BUDGET_S", 999)
    @patch("config.LLM_FALLBACK_PENDING_ENABLED", True)
    @patch("config.MAX_ZERO_MATCH_ITEMS", 1)
    @patch("config.ZERO_MATCH_VALUE_RATIO", 1.0)
    def test_cap_one(self):
        """cap=1 → only 1 item classified, the highest-value one."""
        licitacoes = [_make_lic(valor=float(i * 1000), idx=i) for i in range(50)]

        result, classified = _run_job(licitacoes)

        assert len(classified) == 1
        cap_pending = [
            lic for lic in licitacoes
            if lic.get("_pending_review_reason") == "zero_match_cap_exceeded"
        ]
        assert len(cap_pending) == 49
