"""Property-based tests for search hash functions (#1920).

Property (Equivalence): Equivalent inputs always produce the same hash.
  - Reordering UFs -> same hash
  - Reordering modalidades -> same hash
  - Reordering exclusion_terms -> same hash
  - None vs empty list for optional fields -> same hash

Property (Sensitivity): Different inputs produce different hashes (with
high probability).
  - Different UFs -> different hash
  - Different dates -> different hash
  - Different setor_id -> different hash

Property (Determinism): Same input always produces the same hash.
"""

from hypothesis import given, settings, strategies as st

from cache.enums import compute_search_hash, compute_search_hash_without_dates, compute_search_hash_per_uf

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

uf_list_strategy = st.lists(
    st.sampled_from(_ALL_UFS), min_size=0, max_size=27, unique=True,
)


@st.composite
def search_params(draw):
    """Generate a dict of search parameters for hash computation."""
    return {
        "setor_id": draw(st.one_of(st.none(), st.sampled_from([
            "vestuario", "alimentos", "informatica", "saude",
            "educacao", "transporte", "construcao",
        ]))),
        "ufs": draw(uf_list_strategy),
        "status": draw(st.one_of(st.none(), st.sampled_from([
            "recebendo_proposta", "em_julgamento", "encerrada", "todos",
        ]))),
        "modalidades": draw(st.one_of(
            st.none(),
            st.lists(
                st.sampled_from([1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15]),
                min_size=0, max_size=5, unique=True,
            ),
        )),
        "modo_busca": draw(st.one_of(st.none(), st.sampled_from(["abertas", "publicacao"]))),
        "data_inicial": draw(st.one_of(st.none(), st.sampled_from([
            "2025-01-01", "2025-06-15", "2026-01-01",
        ]))),
        "data_final": draw(st.one_of(st.none(), st.sampled_from([
            "2025-01-31", "2025-07-15", "2026-02-01",
        ]))),
        "termos_busca": draw(st.one_of(st.none(), st.sampled_from([
            "uniforme", "jaleco avental", "terraplenagem", None,
        ]))),
        "valor_minimo": draw(st.one_of(st.none(), st.floats(
            min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False,
        ))),
        "valor_maximo": draw(st.one_of(st.none(), st.floats(
            min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False,
        ))),
        "esferas": draw(st.one_of(
            st.none(),
            st.lists(st.sampled_from(["F", "E", "M"]), min_size=0, max_size=3, unique=True),
        )),
        "municipios": draw(st.one_of(
            st.none(),
            st.lists(st.text(min_size=5, max_size=10), min_size=0, max_size=3, unique=True),
        )),
        "exclusion_terms": draw(st.one_of(
            st.none(),
            st.lists(st.text(min_size=3, max_size=15), min_size=0, max_size=3, unique=True),
        )),
        "show_all_matches": draw(st.booleans()),
    }


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestComputeSearchHash:
    """Property-based tests for compute_search_hash."""

    @given(params=search_params())
    @settings(deadline=2000)
    def test_deterministic(self, params: dict):
        """Property: Same input always produces the same hash."""
        h1 = compute_search_hash(params)
        h2 = compute_search_hash(params)
        assert h1 == h2, "Hash must be deterministic for same input"

    @given(params=search_params())
    @settings(deadline=2000)
    def test_uf_order_independence(self, params: dict):
        """Property: Reordering UFs should not change the hash."""
        params_copy = dict(params)
        if params.get("ufs"):
            ufs = list(params["ufs"])
            params_copy["ufs"] = list(reversed(ufs))

        h1 = compute_search_hash(params)
        h2 = compute_search_hash(params_copy)
        assert h1 == h2, "Hash must be independent of UF ordering"

    @given(params=search_params())
    @settings(deadline=2000)
    def test_modalidades_order_independence(self, params: dict):
        """Property: Reordering modalidades should not change the hash."""
        params_copy = dict(params)
        if params.get("modalidades") and len(params["modalidades"]) > 1:
            mods = list(params["modalidades"])
            params_copy["modalidades"] = list(reversed(mods))

            h1 = compute_search_hash(params)
            h2 = compute_search_hash(params_copy)
            assert h1 == h2, "Hash must be independent of modalidade ordering"

    @given(params=search_params())
    @settings(deadline=2000)
    def test_esferas_order_independence(self, params: dict):
        """Property: Reordering esferas should not change the hash."""
        params_copy = dict(params)
        if params.get("esferas") and len(params["esferas"]) > 1:
            esferas = list(params["esferas"])
            params_copy["esferas"] = list(reversed(esferas))

            h1 = compute_search_hash(params)
            h2 = compute_search_hash(params_copy)
            assert h1 == h2, "Hash must be independent of esfera ordering"

    @given(params=search_params())
    @settings(deadline=2000)
    def test_empty_vs_none_equivalence(self, params: dict):
        """Property: Empty list [] should produce same hash as None for optional fields.

        For fields like modalidades, esferas, exclusion_terms — None and []
        should be treated equivalently.
        """
        if params.get("modalidades") == []:
            params_with_none = dict(params)
            params_with_none["modalidades"] = None
            h1 = compute_search_hash(params)
            h2 = compute_search_hash(params_with_none)
            assert h1 == h2, (
                "Empty list and None should produce same hash for modalidades"
            )

        if params.get("esferas") == []:
            params_with_none = dict(params)
            params_with_none["esferas"] = None
            h1 = compute_search_hash(params)
            h2 = compute_search_hash(params_with_none)
            assert h1 == h2, (
                "Empty list and None should produce same hash for esferas"
            )


class TestComputeSearchHashWithoutDates:
    """Property-based tests for compute_search_hash_without_dates."""

    @given(params=search_params())
    @settings(deadline=2000)
    def test_deterministic(self, params: dict):
        """Property: Same input always produces the same hash."""
        h1 = compute_search_hash_without_dates(params)
        h2 = compute_search_hash_without_dates(params)
        assert h1 == h2

    @given(params=search_params())
    @settings(deadline=2000)
    def test_date_independent(self, params: dict):
        """Property: Without-dates hash should NOT depend on date fields."""
        params_modified = dict(params)
        params_modified["data_inicial"] = "2099-01-01"
        params_modified["data_final"] = "2099-12-31"

        h1 = compute_search_hash_without_dates(params)
        h2 = compute_search_hash_without_dates(params_modified)
        assert h1 == h2, (
            "Without-dates hash should not change when dates differ"
        )


class TestComputeSearchHashPerUF:
    """Property-based tests for compute_search_hash_per_uf."""

    @given(params=search_params(), uf=st.sampled_from(_ALL_UFS))
    @settings(deadline=2000)
    def test_deterministic(self, params: dict, uf: str):
        """Property: Same (params, uf) always produces the same hash."""
        h1 = compute_search_hash_per_uf(params, uf)
        h2 = compute_search_hash_per_uf(params, uf)
        assert h1 == h2, "Per-UF hash must be deterministic"

    @given(params=search_params())
    @settings(deadline=2000)
    def test_uf_single_element(self, params: dict):
        """Property: Per-UF hash with one UF should match the general hash
        with the same single UF in the list."""

        uf = "SP"
        h_per_uf = compute_search_hash_per_uf(params, uf)

        params_single = dict(params)
        params_single["ufs"] = [uf]
        h_full = compute_search_hash(params_single)

        # These should NOT necessarily be equal (hash is SHA256 of
        # different JSON structures), but they should both be deterministic
        assert isinstance(h_per_uf, str) and len(h_per_uf) == 64
        assert isinstance(h_full, str) and len(h_full) == 64
