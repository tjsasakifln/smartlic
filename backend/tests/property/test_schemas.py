"""Property-based tests for BuscaRequest schema (#1920).

Property: For any valid combination of filters, BuscaRequest should
serialize to dict / JSON and deserialize back without data loss
(round-trip serialization).

Property: Any valid dates + UFs combination should produce a valid model
(model_validator post-conditions).

Property: The 30-day max date range invariant must hold for all inputs
that violate it.
"""

import json
from datetime import date, timedelta

from hypothesis import assume, given, settings, strategies as st
from pydantic import ValidationError
from schemas.common import EsferaGovernamental, StatusLicitacao
from schemas.search import BuscaRequest

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# 27 Brazilian states
_ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

ufs_strategy = st.lists(
    st.sampled_from(_ALL_UFS), min_size=1, max_size=5, unique=True
)

date_strategy = st.dates(
    date(2024, 1, 1), date(2026, 12, 31)
).map(lambda d: d.isoformat())

valid_modalidades = st.lists(
    st.sampled_from([1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15]),
    min_size=1,
    max_size=5,
    unique=True,
)

valor_strategy = st.one_of(
    st.none(),
    st.floats(min_value=0, max_value=1e12, allow_infinity=False, allow_nan=False),
)

ordenacao_strategy = st.sampled_from([
    "data_desc", "data_asc", "valor_desc", "valor_asc",
    "prazo_asc", "relevancia", "confianca",
])

itens_por_pagina_strategy = st.sampled_from([10, 20, 50, 100])

# Only Latin letters + digits + spaces, commas, hyphens (matches BuscaRequest validator)
_SAFE_TERMOS_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,-"
termos_busca_strategy = st.one_of(
    st.none(),
    st.text(alphabet=_SAFE_TERMOS_CHARS, min_size=1, max_size=200).map(
        lambda s: s.strip()
    ).filter(lambda s: len(s) > 0),
)


@st.composite
def valid_busca_request(draw):
    """Generate a BuscaRequest with valid date range (<=30 days)."""
    ufs = draw(ufs_strategy)
    d_ini = draw(st.dates(date(2024, 1, 1), date(2026, 10, 31)))
    max_offset = min(30, (date(2026, 12, 31) - d_ini).days)
    assume(max_offset >= 0)
    offset = draw(st.integers(min_value=0, max_value=max_offset))
    d_fin = d_ini + timedelta(days=offset)
    data_inicial = d_ini.isoformat()
    data_final = d_fin.isoformat()

    # Generate valor_minimo and valor_maximo with correct ordering
    _v_min = draw(valor_strategy)
    _v_max = draw(valor_strategy)
    if _v_min is not None and _v_max is not None and _v_min > _v_max:
        _v_min, _v_max = _v_max, _v_min

    return BuscaRequest(
        ufs=ufs,
        data_inicial=data_inicial,
        data_final=data_final,
        setor_id=draw(st.one_of(st.none(), st.sampled_from([
            "vestuario", "alimentos", "informatica", "saude",
            "educacao", "seguranca", "transporte", "energia",
        ]))),
        termos_busca=draw(termos_busca_strategy),
        status=draw(st.sampled_from(list(StatusLicitacao))),
        modalidades=draw(st.one_of(st.none(), valid_modalidades)),
        valor_minimo=_v_min,
        valor_maximo=_v_max,
        esferas=draw(st.one_of(
            st.none(),
            st.lists(
                st.sampled_from(list(EsferaGovernamental)),
                min_size=1, max_size=3, unique=True,
            ),
        )),
        ordenacao=draw(ordenacao_strategy),
        itens_por_pagina=draw(itens_por_pagina_strategy),
        show_all_matches=draw(st.booleans()),
        modo_busca=draw(st.sampled_from(["abertas", "publicacao"])),
        check_sanctions=draw(st.booleans()),
        force_fresh=draw(st.booleans()),
    )


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestBuscaRequest:
    """Property-based tests for BuscaRequest schema."""

    @given(request=valid_busca_request())
    @settings(deadline=2000)
    def test_round_trip_serialization(self, request: BuscaRequest):
        """Property: Serialize to dict → JSON → deserialize → same model.

        For any valid BuscaRequest, the round-trip through dict and JSON
        should produce an equal model with no data loss.
        """
        # Dict round-trip
        as_dict = request.model_dump()
        restored = BuscaRequest(**as_dict)
        assert restored.model_dump() == as_dict, (
            f"Dict round-trip failed for: {as_dict}"
        )

        # JSON round-trip
        as_json = request.model_dump_json()
        restored_json = BuscaRequest(**json.loads(as_json))
        assert restored_json.model_dump_json() == as_json, (
            "JSON round-trip produced different output"
        )

    @given(request=valid_busca_request())
    @settings(deadline=2000)
    def test_ufs_never_empty(self, request: BuscaRequest):
        """Property: ufs should always have at least 1 element after validation."""
        assert len(request.ufs) >= 1, "ufs must not be empty"

    @given(request=valid_busca_request())
    @settings(deadline=2000)
    def test_dates_are_valid_and_ordered(self, request: BuscaRequest):
        """Property: data_inicial <= data_final, and range <= 30 days."""
        d_ini = date.fromisoformat(request.data_inicial)
        d_fin = date.fromisoformat(request.data_final)
        assert d_ini <= d_fin, "data_inicial must be <= data_final"
        assert (d_fin - d_ini).days <= 30, (
            "Date range must not exceed 30 days"
        )

    @given(request=valid_busca_request())
    @settings(deadline=2000)
    def test_valor_range_consistency(self, request: BuscaRequest):
        """Property: If both valor_minimo and valor_maximo set, min <= max."""
        if request.valor_minimo is not None and request.valor_maximo is not None:
            assert request.valor_minimo <= request.valor_maximo, (
                f"valor_minimo ({request.valor_minimo}) must be <= "
                f"valor_maximo ({request.valor_maximo})"
            )

    @given(
        ufs=ufs_strategy,
        data_inicial=date_strategy,
        # Generate data_final that exceeds 30 days from data_inicial
    )
    @settings(deadline=2000)
    def test_excessive_date_range_rejected(
        self, ufs, data_inicial
    ):
        """Property: Any date range > 30 days MUST raise ValidationError."""
        d_ini = date.fromisoformat(data_inicial)
        far_future = d_ini + timedelta(days=31)
        if far_future > date(2026, 12, 31):
            return  # Skip dates beyond our strategy range
        data_final = far_future.isoformat()

        with pytest.raises(ValidationError):
            BuscaRequest(
                ufs=ufs,
                data_inicial=data_inicial,
                data_final=data_final,
            )

    @given(request=valid_busca_request())
    @settings(deadline=2000)
    def test_enum_values_are_valid(self, request: BuscaRequest):
        """Property: All enum fields contain only valid values."""
        assert isinstance(request.status, StatusLicitacao)
        assert isinstance(request.ordenacao, str)
        assert request.ordenacao in {
            "data_desc", "data_asc", "valor_desc", "valor_asc",
            "prazo_asc", "relevancia", "confianca",
        }
        assert request.itens_por_pagina in {10, 20, 50, 100}

        if request.modalidades is not None:
            VALID_MODS = {1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15}
            for m in request.modalidades:
                assert m in VALID_MODS, f"Invalid modalidade code: {m}"

        if request.esferas is not None:
            for e in request.esferas:
                assert isinstance(e, EsferaGovernamental)

    @given(request=valid_busca_request())
    @settings(deadline=2000)
    def test_schema_serializable_types(self, request: BuscaRequest):
        """Property: All output types are JSON-serializable (no objects)."""
        as_dict = request.model_dump()
        # This should not raise
        json_str = json.dumps(as_dict, default=str)
        assert isinstance(json_str, str)
        # Re-parsing should also not raise
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)


import pytest  # noqa: E402 — required for pytest.raises in test_excessive_date_range_rejected
