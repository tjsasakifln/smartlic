"""Property-based tests for filter pipeline (aplicar_todos_filtros) (#1920).

Property (UF Filter Monotonicity): For any input, the UF filter stage
should reduce or maintain the number of records — never increase it.

Property (Keyword Filter Monotonicity): After UF filtering, applying
keyword matching should reduce or maintain the count.

Property (Idempotency of UF filter): Filtering by the same UF set
twice should produce the same output.
"""

from hypothesis import given, settings, strategies as st

from filter.pipeline import aplicar_todos_filtros

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

# Generic procurement-like object text for strategy
objeto_text_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P"),
        whitelist_characters=" /-,",
    ),
    min_size=0,
    max_size=200,
).map(lambda s: s.strip())


@st.composite
def bid_document(draw):
    """Generate a mock bid document (dict) similar to what the filter pipeline expects."""
    uf = draw(st.sampled_from(_ALL_UFS))
    modalidade = draw(st.sampled_from([1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15]))
    valor = draw(st.one_of(
        st.none(),
        st.floats(
            min_value=0, max_value=1e9,
            allow_infinity=False, allow_nan=False,
        ),
    ))
    return {
        "numeroControlePNCP": draw(st.text(min_size=5, max_size=30)),
        "objetoCompra": draw(objeto_text_strategy),
        "valorTotalEstimado": valor,
        "nomeOrgao": draw(objeto_text_strategy),
        "cnpjOrgao": draw(st.text("0123456789", min_size=14, max_size=14)),
        "uf": uf,
        "municipio": draw(st.text(min_size=0, max_size=50)),
        "dataPublicacaoPncp": draw(st.one_of(st.none(), st.sampled_from([
            "2025-01-01T10:00:00", "2025-06-15T14:30:00", "2026-01-01T08:00:00",
        ]))),
        "dataAberturaProposta": draw(st.one_of(st.none(), st.sampled_from([
            "2025-01-15T10:00:00", "2025-07-01T09:00:00",
        ]))),
        "modalidadeId": modalidade,
        "modalidadeNome": draw(st.text(min_size=3, max_size=30)),
        "situacaoCompraNome": draw(st.sampled_from([
            "", "Recebendo Propostas", "Em Julgamento", "Encerrada",
        ])),
        "_source": draw(st.sampled_from(["PNCP", "PORTAL_COMPRAS"])),
    }


@st.composite
def bids_with_ufs(draw):
    """Generate a list of bid documents and a set of selected UFs."""
    n_bids = draw(st.integers(min_value=0, max_value=30))
    bids = [draw(bid_document()) for _ in range(n_bids)]

    # Selected UFs — maybe a subset, maybe a superset, maybe random
    selected_ufs = draw(
        st.sets(st.sampled_from(_ALL_UFS), min_size=1, max_size=10)
    )

    return bids, selected_ufs


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestFilterPipelineMonotonicity:
    """Property: Filter stages are monotonic (never increase count)."""

    @given(config=bids_with_ufs())
    @settings(deadline=2000)
    def test_uf_filter_monotonic(self, config):
        """Property: UF filter reduces or maintains count (never increases).

        For any set of bids and any set of selected UFs, the output of
        aplicar_todos_filtros with only UF filtering active must have
        length <= input length.
        """
        bids, selected_ufs = config

        # Apply all filters with UF only (no keyword filtering)
        aprovadas, stats = aplicar_todos_filtros(
            licitacoes=bids,
            ufs_selecionadas=selected_ufs,
            status="todos",       # No status filter (pass through)
            keywords=set(),        # Empty keywords = pass through
            modo_busca="publicacao",
        )

        assert len(aprovadas) <= len(bids), (
            f"UF filter increased count from {len(bids)} to {len(aprovadas)}"
        )

    @given(config=bids_with_ufs())
    @settings(deadline=2000)
    def test_uf_filter_rejects_outside_ufs(self, config):
        """Property: After UF filtering, every bid has a UF in the selected set."""
        bids, selected_ufs = config

        aprovadas, stats = aplicar_todos_filtros(
            licitacoes=bids,
            ufs_selecionadas=selected_ufs,
            status="todos",
            keywords=set(),
            modo_busca="publicacao",
        )

        for bid in aprovadas:
            assert bid["uf"] in selected_ufs, (
                f"Bid UF '{bid['uf']}' not in selected set {selected_ufs}"
            )

    @given(config=bids_with_ufs())
    @settings(deadline=2000)
    def test_rejected_uf_count_matches_stats(self, config):
        """Property: rejeitadas_uf count equals bids with UF not in selected set
        (for bids that have a non-empty UF).

        Bids with empty UF are also counted as rejected.
        """
        bids, selected_ufs = config

        aprovadas, stats = aplicar_todos_filtros(
            licitacoes=bids,
            ufs_selecionadas=selected_ufs,
            status="todos",
            keywords=set(),
            modo_busca="publicacao",
        )

        # Compute expected rejects manually
        expected_rejects = sum(
            1 for b in bids
            if b.get("uf", "") not in selected_ufs
        )
        assert stats["rejeitadas_uf"] == expected_rejects, (
            f"Expected {expected_rejects} UF rejects, got {stats['rejeitadas_uf']}"
        )

    @given(
        bids=st.lists(bid_document(), min_size=0, max_size=15),
    )
    @settings(deadline=2000)
    def test_uf_filter_idempotent(self, bids: list):
        """Property: Applying the same UF filter twice yields same output."""
        selected = {"SP", "RJ", "MG"}

        aprovadas_1, _ = aplicar_todos_filtros(
            licitacoes=bids,
            ufs_selecionadas=selected,
            status="todos",
            keywords=set(),
            modo_busca="publicacao",
        )

        aprovadas_2, _ = aplicar_todos_filtros(
            licitacoes=aprovadas_1,
            ufs_selecionadas=selected,
            status="todos",
            keywords=set(),
            modo_busca="publicacao",
        )

        assert len(aprovadas_2) == len(aprovadas_1), (
            "Second UF filter pass changed count — not idempotent"
        )

    @given(
        bids=st.lists(bid_document(), min_size=0, max_size=20),
        ufs=st.sets(st.sampled_from(_ALL_UFS), min_size=1, max_size=5),
    )
    @settings(deadline=2000)
    def test_value_filter_monotonic(
        self, bids: list, ufs: set
    ):
        """Property: Value filter within UF-filtered result should
        also be monotonic (reduces or maintains count)."""
        aprovadas_uf, _ = aplicar_todos_filtros(
            licitacoes=bids,
            ufs_selecionadas=ufs,
            status="todos",
            keywords=set(),
            modo_busca="publicacao",
        )

        # Apply value filter on top of UF filter
        aprovadas_valor, _ = aplicar_todos_filtros(
            licitacoes=aprovadas_uf,
            ufs_selecionadas=ufs,
            status="todos",
            keywords=set(),
            valor_min=10000,
            valor_max=500000,
            modo_busca="publicacao",
        )

        assert len(aprovadas_valor) <= len(aprovadas_uf), (
            f"Value filter increased from {len(aprovadas_uf)} "
            f"to {len(aprovadas_valor)}"
        )
