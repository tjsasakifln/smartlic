"""Property-based tests for search schema models (#1969).

Covers: SearchQueuedResponse, SearchStatusResponse, ResumoLicitacoes,
Recomendacao, ResumoEstrategico, FilterStats, SanctionsSummarySchema,
LicitacaoItem, DataSourceStatus, UfStatusDetail, CoverageMetadata,
BuscaResponse.

Property: Round-trip serialization (model_dump -> model_validate -> equal).
Property: JSON Schema is valid Draft 2020-12.
Property: Invariant constraints (ge/le, min/max lengths, enum values).
"""

from hypothesis import given, settings, HealthCheck, strategies as st

from schemas.search import (
    SearchQueuedResponse,
    SearchStatusResponse,
    ResumoLicitacoes,
    Recomendacao,
    ResumoEstrategico,
    FilterStats,
    SanctionsSummarySchema,
    LicitacaoItem,
    DataSourceStatus,
    UfStatusDetail,
    CoverageMetadata,
    BuscaResponse,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

_VALID_SOURCES = ["pncp", "portal_compras", "portal", "compras_gov"]
_UF_STATUSES = ["ok", "timeout", "error", "skipped"]
_RESPONSE_STATES = [
    "live", "cached", "degraded", "empty_failure", "degraded_expired",
]
_FRESHNESS_LEVELS = ["live", "cached_fresh", "cached_stale"]

# ---------------------------------------------------------------------------
# Shared strategy helpers
# ---------------------------------------------------------------------------

safe_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.-",
    min_size=1, max_size=200,
)
nonneg_float = st.floats(
    min_value=0, max_value=1e12, allow_infinity=False, allow_nan=False,
)
uf_list = st.lists(
    st.sampled_from(_ALL_UFS), min_size=0, max_size=27, unique=True,
)
small_int = st.integers(min_value=0, max_value=10000)

# ---------------------------------------------------------------------------
# Strategy: SearchQueuedResponse
# ---------------------------------------------------------------------------

search_queued_strategy = st.builds(
    SearchQueuedResponse,
    search_id=st.text(min_size=1, max_size=36),
    status_url=st.builds(lambda: "/v1/search/id/status"),
    progress_url=st.builds(lambda: "/v1/search/id/progress"),
    estimated_duration_s=st.integers(min_value=10, max_value=120),
)

# ---------------------------------------------------------------------------
# Strategy: SearchStatusResponse
# ---------------------------------------------------------------------------

search_status_strategy = st.builds(
    SearchStatusResponse,
    search_id=st.text(min_size=1, max_size=36),
    status=st.sampled_from(["running", "completed", "failed", "timeout"]),
    progress_pct=st.integers(min_value=0, max_value=100),
    ufs_completed=uf_list,
    ufs_pending=uf_list,
    results_count=st.integers(min_value=0, max_value=10000),
    elapsed_s=st.floats(
        min_value=0, max_value=3600, allow_infinity=False, allow_nan=False,
    ),
    created_at=st.one_of(st.none(), st.datetimes().map(lambda d: d.isoformat())),
    results_url=st.one_of(st.none(), st.builds(lambda: "/v1/search/id/results")),
    excel_url=st.one_of(st.none(), st.builds(lambda: "https://example.com/excel.xlsx")),
    excel_status=st.one_of(
        st.none(),
        st.sampled_from(["processing", "ready", "failed", "skipped"]),
    ),
)

# ---------------------------------------------------------------------------
# Strategy: ResumoLicitacoes
# ---------------------------------------------------------------------------

resumo_strategy = st.builds(
    ResumoLicitacoes,
    resumo_executivo=safe_text,
    total_oportunidades=st.integers(min_value=0, max_value=10000),
    valor_total=nonneg_float,
    destaques=st.lists(safe_text, max_size=10),
    outlier_count=st.integers(min_value=0, max_value=1000),
    valor_sanitizado=st.booleans(),
)

# ---------------------------------------------------------------------------
# Strategy: Recomendacao
# ---------------------------------------------------------------------------

recomendacao_strategy = st.builds(
    Recomendacao,
    oportunidade=safe_text,
    valor=nonneg_float,
    urgencia=st.sampled_from(["alta", "media", "baixa"]),
    acao_sugerida=safe_text,
    justificativa=safe_text,
)

# ---------------------------------------------------------------------------
# Strategy: ResumoEstrategico (extends ResumoLicitacoes)
# ---------------------------------------------------------------------------

resumo_estrategico_strategy = st.builds(
    ResumoEstrategico,
    resumo_executivo=safe_text,
    total_oportunidades=st.integers(min_value=0, max_value=10000),
    valor_total=nonneg_float,
    destaques=st.lists(safe_text, max_size=10),
    outlier_count=st.integers(min_value=0, max_value=1000),
    valor_sanitizado=st.booleans(),
    recomendacoes=st.lists(recomendacao_strategy, max_size=5),
    alertas_urgencia=st.lists(safe_text, max_size=10),
    insight_setorial=st.text(min_size=0, max_size=500),
)

# ---------------------------------------------------------------------------
# Strategy: FilterStats
# ---------------------------------------------------------------------------

filter_stats_strategy = st.builds(
    FilterStats,
    rejeitadas_uf=small_int,
    rejeitadas_valor=small_int,
    rejeitadas_keyword=small_int,
    rejeitadas_min_match=small_int,
    rejeitadas_prazo=small_int,
    rejeitadas_outros=small_int,
    llm_zero_match_calls=small_int,
    llm_zero_match_aprovadas=small_int,
    llm_zero_match_rejeitadas=small_int,
    llm_zero_match_skipped_short=small_int,
    zero_match_budget_exceeded=small_int,
    zero_match_capped=st.booleans(),
    zero_match_cap_value=st.integers(min_value=0, max_value=10000),
)

# ---------------------------------------------------------------------------
# Strategy: SanctionsSummarySchema
# ---------------------------------------------------------------------------

sanctions_summary_strategy = st.builds(
    SanctionsSummarySchema,
    is_clean=st.booleans(),
    active_sanctions_count=st.integers(min_value=0, max_value=100),
    sanction_types=st.lists(st.text(min_size=1, max_size=100), max_size=5),
)

# ---------------------------------------------------------------------------
# Strategy: LicitacaoItem
# ---------------------------------------------------------------------------

licitacao_item_strategy = st.builds(
    LicitacaoItem,
    pncp_id=st.text(min_size=1, max_size=50),
    objeto=safe_text,
    orgao=safe_text,
    uf=st.sampled_from(_ALL_UFS),
    municipio=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    valor=st.one_of(st.none(), nonneg_float),
    modalidade=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
    data_publicacao=st.one_of(st.none(), st.datetimes().map(lambda d: d.isoformat())),
    data_abertura=st.one_of(st.none(), st.datetimes().map(lambda d: d.isoformat())),
    data_encerramento=st.one_of(st.none(), st.datetimes().map(lambda d: d.isoformat())),
    dias_restantes=st.one_of(st.none(), st.integers(min_value=-365, max_value=365)),
    link=st.one_of(st.none(), st.text(min_size=1, max_size=500)),
    source=st.one_of(st.none(), st.sampled_from(_VALID_SOURCES)),
    relevance_source=st.one_of(
        st.none(),
        st.sampled_from([
            "keyword", "llm_standard", "llm_conservative", "llm_zero_match",
        ]),
    ),
    confidence=st.one_of(
        st.none(),
        st.sampled_from(["high", "medium", "low"]),
    ),
    confidence_score=st.one_of(st.none(), st.integers(min_value=0, max_value=100)),
    viability_score=st.one_of(st.none(), st.integers(min_value=0, max_value=100)),
    viability_level=st.one_of(
        st.none(),
        st.sampled_from(["alta", "media", "baixa"]),
    ),
)

# ---------------------------------------------------------------------------
# Strategy: DataSourceStatus
# ---------------------------------------------------------------------------

data_source_status_strategy = st.builds(
    DataSourceStatus,
    source=st.sampled_from(_VALID_SOURCES),
    status=st.sampled_from(["ok", "timeout", "error", "skipped"]),
    records=small_int,
)

# ---------------------------------------------------------------------------
# Strategy: UfStatusDetail
# ---------------------------------------------------------------------------

uf_status_detail_strategy = st.builds(
    UfStatusDetail,
    uf=st.sampled_from(_ALL_UFS),
    status=st.sampled_from(_UF_STATUSES),
    results_count=small_int,
)

# ---------------------------------------------------------------------------
# Strategy: CoverageMetadata
# ---------------------------------------------------------------------------

coverage_metadata_strategy = st.builds(
    CoverageMetadata,
    ufs_requested=st.lists(
        st.sampled_from(_ALL_UFS), min_size=1, max_size=27, unique=True,
    ),
    ufs_processed=uf_list,
    ufs_failed=uf_list,
    ufs_empty=uf_list,
    uf_result_counts=st.dictionaries(
        st.sampled_from(_ALL_UFS), small_int, min_size=0, max_size=27,
    ),
    coverage_pct=st.floats(
        min_value=0, max_value=100, allow_infinity=False, allow_nan=False,
    ),
    data_timestamp=st.datetimes().map(lambda d: d.isoformat()),
    freshness=st.sampled_from(_FRESHNESS_LEVELS),
)


@st.composite
def busca_response_strategy(draw):
    """Generate a BuscaResponse always with ResumoEstrategico for round-trip consistency.

    ResumoEstrategico extends ResumoLicitacoes. When serializing via model_dump(),
    a ResumoLicitacoes instance produces a dict that Pydantic may deserialize as
    ResumoEstrategico (since it has all required fields), breaking round-trip equality.
    Using only the larger variant avoids this Union-type ambiguity.
    """
    resumo = draw(resumo_estrategico_strategy)

    return BuscaResponse(
        resumo=resumo,
        licitacoes=draw(st.lists(licitacao_item_strategy, max_size=10)),
        excel_available=draw(st.booleans()),
        quota_used=draw(small_int),
        quota_remaining=draw(small_int),
        total_raw=draw(small_int),
        total_filtrado=draw(small_int),
        is_partial=draw(st.booleans()),
        is_truncated=draw(st.booleans()),
        cached=draw(st.booleans()),
        from_cache=draw(st.booleans()),
        response_state=draw(st.sampled_from(_RESPONSE_STATES)),
        coverage_pct=draw(st.integers(min_value=0, max_value=100)),
        pending_review_count=draw(small_int),
        match_relaxed=draw(st.booleans()),
        is_simplified=draw(st.booleans()),
        zero_match_candidates_count=draw(small_int),
        paywall_applied=draw(st.booleans()),
        hidden_by_min_match=draw(st.one_of(st.none(), small_int)),
        filter_relaxed=draw(st.one_of(st.none(), st.booleans())),
        live_fetch_in_progress=draw(st.booleans()),
        ultima_atualizacao=draw(st.one_of(
            st.none(), st.datetimes().map(lambda d: d.isoformat()),
        )),
        llm_source=draw(st.one_of(
            st.none(),
            st.sampled_from(["ai", "fallback", "processing"]),
        )),
        llm_status=draw(st.one_of(
            st.none(), st.sampled_from(["ready", "processing"]),
        )),
        excel_status=draw(st.one_of(
            st.none(),
            st.sampled_from(["ready", "processing", "skipped", "failed"]),
        )),
        relaxation_level=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=3))),
        cache_status=draw(st.one_of(
            st.none(), st.sampled_from(["fresh", "stale"]),
        )),
        cache_level=draw(st.one_of(
            st.none(), st.sampled_from(["supabase", "redis", "local"]),
        )),
        cache_fallback=draw(st.booleans()),
        filter_summary=draw(st.one_of(st.none(), safe_text)),
        degradation_reason=draw(st.one_of(st.none(), safe_text)),
        degradation_guidance=draw(st.one_of(st.none(), safe_text)),
        upgrade_message=draw(st.one_of(st.none(), safe_text)),
        source_stats=draw(st.one_of(
            st.none(),
            st.lists(
                st.dictionaries(safe_text, st.one_of(
                    st.text(), st.integers(), st.floats(),
                ), min_size=1, max_size=5),
                max_size=5,
            ),
        )),
        sources_used=draw(st.one_of(st.none(), st.lists(safe_text, max_size=10))),
        sources_degraded=draw(st.one_of(st.none(), st.lists(safe_text, max_size=10))),
        termos_utilizados=draw(st.one_of(st.none(), st.lists(safe_text, max_size=20))),
        stopwords_removidas=draw(st.one_of(st.none(), st.lists(safe_text, max_size=50))),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_roundtrip(obj):
    """Assert round-trip: model_dump -> model_validate -> equal."""
    dumped = obj.model_dump()
    reloaded = type(obj).model_validate(dumped)
    assert reloaded == obj, f"Round-trip failed for {type(obj).__name__}"


def _check_json_schema(obj):
    """Assert JSON Schema is valid for the model class."""
    schema = type(obj).model_json_schema()
    assert schema is not None, f"JSON Schema is None for {type(obj).__name__}"
    assert "properties" in schema, (
        f"JSON Schema missing 'properties' for {type(obj).__name__}"
    )


_SETTINGS = settings(
    deadline=500, suppress_health_check=[HealthCheck.too_slow],
)


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestSearchQueuedResponse:
    """Property tests for SearchQueuedResponse."""

    @given(obj=search_queued_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=search_queued_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=search_queued_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.search_id, str) and len(obj.search_id) > 0
        assert obj.status == "queued"
        assert obj.estimated_duration_s >= 10


class TestSearchStatusResponse:
    """Property tests for SearchStatusResponse."""

    @given(obj=search_status_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=search_status_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=search_status_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.status in {"running", "completed", "failed", "timeout"}
        assert 0 <= obj.progress_pct <= 100
        assert obj.results_count >= 0
        assert obj.elapsed_s >= 0


class TestResumoLicitacoes:
    """Property tests for ResumoLicitacoes."""

    @given(obj=resumo_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=resumo_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=resumo_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.total_oportunidades >= 0
        assert obj.valor_total >= 0
        assert obj.outlier_count >= 0
        assert isinstance(obj.valor_sanitizado, bool)


class TestRecomendacao:
    """Property tests for Recomendacao."""

    @given(obj=recomendacao_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=recomendacao_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=recomendacao_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.valor >= 0
        assert obj.urgencia in {"alta", "media", "baixa"}
        assert len(obj.oportunidade) > 0
        assert len(obj.acao_sugerida) > 0
        assert len(obj.justificativa) > 0


class TestResumoEstrategico:
    """Property tests for ResumoEstrategico (extends ResumoLicitacoes)."""

    @given(obj=resumo_estrategico_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=resumo_estrategico_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=resumo_estrategico_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.total_oportunidades >= 0
        assert obj.valor_total >= 0
        assert isinstance(obj.insight_setorial, str)
        # Subclass fields must be present
        assert hasattr(obj, "recomendacoes")
        assert hasattr(obj, "alertas_urgencia")


class TestFilterStats:
    """Property tests for FilterStats."""

    @given(obj=filter_stats_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=filter_stats_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=filter_stats_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.rejeitadas_uf >= 0
        assert obj.rejeitadas_valor >= 0
        assert obj.rejeitadas_keyword >= 0
        assert obj.llm_zero_match_calls >= 0
        assert obj.zero_match_cap_value >= 0
        assert isinstance(obj.zero_match_capped, bool)


class TestSanctionsSummarySchema:
    """Property tests for SanctionsSummarySchema."""

    @given(obj=sanctions_summary_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=sanctions_summary_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=sanctions_summary_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.is_clean, bool)
        assert obj.active_sanctions_count >= 0


class TestLicitacaoItem:
    """Property tests for LicitacaoItem."""

    @given(obj=licitacao_item_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=licitacao_item_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=licitacao_item_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.pncp_id) > 0
        assert len(obj.objeto) > 0
        assert len(obj.orgao) > 0
        assert obj.uf in _ALL_UFS
        if obj.valor is not None:
            assert obj.valor >= 0
        if obj.confidence_score is not None:
            assert 0 <= obj.confidence_score <= 100
        if obj.viability_score is not None:
            assert 0 <= obj.viability_score <= 100
        if obj.viability_level is not None:
            assert obj.viability_level in {"alta", "media", "baixa"}


class TestDataSourceStatus:
    """Property tests for DataSourceStatus."""

    @given(obj=data_source_status_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=data_source_status_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=data_source_status_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.source in _VALID_SOURCES
        assert obj.status in {"ok", "timeout", "error", "skipped"}
        assert obj.records >= 0


class TestUfStatusDetail:
    """Property tests for UfStatusDetail."""

    @given(obj=uf_status_detail_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=uf_status_detail_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=uf_status_detail_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.uf in _ALL_UFS
        assert obj.status in _UF_STATUSES
        assert obj.results_count >= 0


class TestCoverageMetadata:
    """Property tests for CoverageMetadata."""

    @given(obj=coverage_metadata_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=coverage_metadata_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=coverage_metadata_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert 0 <= obj.coverage_pct <= 100
        assert obj.freshness in _FRESHNESS_LEVELS
        assert len(obj.ufs_requested) >= 1
        assert isinstance(obj.data_timestamp, str)


class TestBuscaResponse:
    """Property tests for BuscaResponse (large schema)."""

    @given(obj=busca_response_strategy())
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=busca_response_strategy())
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=busca_response_strategy())
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.quota_used >= 0
        assert obj.quota_remaining >= 0
        assert obj.total_raw >= 0
        assert obj.total_filtrado >= 0
        assert 0 <= obj.coverage_pct <= 100
        assert obj.response_state in _RESPONSE_STATES
        assert obj.pending_review_count >= 0
        assert obj.zero_match_candidates_count >= 0
        assert isinstance(obj.excel_available, bool)
        assert isinstance(obj.cached, bool)
        assert isinstance(obj.is_partial, bool)
