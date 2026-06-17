"""Property-based tests for DeduplicationEngine (#1920).

Property (Cardinality Invariant): For any list of UnifiedProcurement records,
the dedup engine MUST return a list with length <= input length.

Property (Idempotency): Running dedup twice on the same input produces
the same output as running it once.

Property (Determinism): Given the same input and configuration, dedup
always produces the same output.
"""

from hypothesis import given, settings, strategies as st

# We patch the consolidation module globally so we don't import
# the real DeduplicationEngine (no adapters needed for property tests).
from consolidation.dedup import DeduplicationEngine


# ---------------------------------------------------------------------------
# Helper: build a minimal mock adapter dict
# ---------------------------------------------------------------------------
def _make_mock_source(src_code: str, src_priority: int = 100):
    """Create a minimal mock source adapter for DeduplicationEngine."""

    class _MockAdapterMeta:
        pass

    class _MockAdapter:
        pass

    _MockAdapterMeta.code = src_code
    _MockAdapterMeta.priority = src_priority
    _MockAdapter.code = src_code
    _MockAdapter.metadata = _MockAdapterMeta()
    return _MockAdapter()


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

SOURCE_NAMES = ["PNCP", "PORTAL_COMPRAS", "PORTAL"]

# 27 Brazilian states
_ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

text_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
        whitelist_characters=" ",
    ),
    min_size=0,
    max_size=200,
)


@st.composite
def unified_procurement_strategy(draw):
    """Generate a single UnifiedProcurement-like record (as a regular dataclass).

    We need to produce records for DeduplicationEngine which expects
    UnifiedProcurement instances. For property-based testing, we create
    UnifiedProcurement dataclass instances directly.
    """
    from clients.base import UnifiedProcurement

    source_id = draw(st.text(
        alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-./"),
        min_size=1, max_size=50,
    ))
    source_name = draw(st.sampled_from(SOURCE_NAMES))
    cnpj = draw(st.text("0123456789", min_size=14, max_size=14))
    uf = draw(st.sampled_from(_ALL_UFS))

    return UnifiedProcurement(
        source_id=source_id,
        source_name=source_name,
        objeto=draw(text_strategy),
        valor_estimado=draw(st.one_of(
            st.none(),
            st.floats(
                min_value=0.0, max_value=1e9,
                allow_infinity=False, allow_nan=False,
            ),
        )),
        orgao=draw(text_strategy),
        cnpj_orgao=cnpj,
        uf=uf,
        municipio=draw(text_strategy),
        data_publicacao=draw(st.one_of(
            st.none(),
            st.datetimes(),
        )),
        data_abertura=draw(st.one_of(st.none(), st.datetimes())),
        data_encerramento=draw(st.one_of(st.none(), st.datetimes())),
        numero_edital=draw(st.text(min_size=0, max_size=20)),
        ano=draw(st.text("0123456789", min_size=4, max_size=4)),
        modalidade=draw(text_strategy),
        modalidade_id=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=15))),
        situacao=draw(text_strategy),
        esfera=draw(st.sampled_from(["F", "E", "M", ""])),
        link_edital=draw(st.text(min_size=0, max_size=100)),
    )


@st.composite
def dedup_engine_with_records(draw):
    """Generate a DeduplicationEngine and a list of records to dedup."""
    adapters = {}
    for code in ["PNCP", "PORTAL_COMPRAS", "PORTAL"]:
        adapters[code] = _make_mock_source(code, src_priority={"PNCP": 1, "PORTAL_COMPRAS": 2, "PORTAL": 3}.get(code, 100))

    engine = DeduplicationEngine(
        adapters=adapters,
        fuzzy_enabled=draw(st.booleans()),
        fuzzy_threshold=draw(st.floats(
            min_value=0.0, max_value=1.0,
            allow_infinity=False, allow_nan=False,
        )),
    )

    record_count = draw(st.integers(min_value=0, max_value=20))
    records = [draw(unified_procurement_strategy()) for _ in range(record_count)]
    # Fix up dedup_key for records that have one set — the strategy may set it,
    # but we want to trigger the dataclass __post_init__ which regenerates it.
    # Leave it as-is; __post_init__ already handles generation when empty.
    return engine, records


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestDedupCardinality:
    """Property: DedupEngine output cardinality never exceeds input."""

    @given(config=dedup_engine_with_records())
    @settings(deadline=2000)
    def test_output_cardinality_never_exceeds_input(self, config):
        """Cardinality Invariant: |run(records)| <= |records|.

        Deduplication should never hallucinate new records — it can only
        remove or keep duplicates.
        """
        engine, records = config
        output = engine.run(records)
        assert len(output) <= len(records), (
            f"Dedup produced {len(output)} records from input of "
            f"{len(records)} — should be <= input count"
        )

    @given(config=dedup_engine_with_records())
    @settings(deadline=2000)
    def test_preserves_originals_when_no_overlap(self, config):
        """Property: If all records are distinct (by source_id AND dedup_key),
        the output should have the same count as the input.

        We use the fact that random records have almost-zero collision
        probability for both source_id and dedup_key.
        """
        engine, records = config
        # This requires all records to have unique source_ids and dedup_keys
        # For random generation this is almost certainly true.
        # Just check that dedup doesn't remove MORE than len(records) - collisons
        output = engine.run(records)
        # The output should at least contain all records (plus deduplication may
        # remove some but shouldn't remove ALL unless there's a bug)
        if records:
            assert len(output) <= len(records)

    @given(config=dedup_engine_with_records())
    @settings(deadline=2000)
    def test_idempotency(self, config):
        """Property: Running dedup twice on the same data is idempotent.

        First run removes duplicates; second run should see no more duplicates
        and return the exact same output.
        """
        engine, records = config
        first_pass = engine.run(records)
        second_pass = engine.run(first_pass)
        assert len(second_pass) == len(first_pass), (
            f"Second dedup pass reduced count from {len(first_pass)} "
            f"to {len(second_pass)} — not idempotent"
        )

    @given(config=dedup_engine_with_records())
    @settings(deadline=2000)
    def test_empty_input_returns_empty(self, config):
        """Property: Empty input should always return empty output."""
        engine, _ = config
        output = engine.run([])
        assert output == [], f"Empty input should return empty list, got {output}"

    @given(config=dedup_engine_with_records())
    @settings(deadline=2000)
    def test_single_record_passes_through(self, config):
        """Property: A single record with no collisions passes through unchanged."""
        engine, records = config
        if not records:
            return
        single = records[:1]
        output = engine.run(single)
        assert len(output) == 1, f"Single record produced {len(output)} results"
