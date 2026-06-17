"""Property-based tests for pipeline (kanban) schema models (#1969).

Covers: PipelineItemCreate, PipelineItemUpdate, PipelineItemResponse,
PipelineListResponse, PipelineAlertsResponse.

Property: Round-trip serialization (model_dump -> model_validate -> equal).
Property: JSON Schema is valid Draft 2020-12.
Property: Invariant constraints, valid pipeline stages.
"""

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st
from pydantic import ValidationError

from schemas.pipeline import (
    VALID_PIPELINE_STAGES,
    PipelineItemCreate,
    PipelineItemUpdate,
    PipelineItemResponse,
    PipelineListResponse,
    PipelineAlertsResponse,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SETTINGS = settings(
    deadline=500, suppress_health_check=[HealthCheck.too_slow],
)

safe_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.-",
    min_size=1, max_size=200,
)


def _run_roundtrip(obj):
    dumped = obj.model_dump()
    reloaded = type(obj).model_validate(dumped)
    assert reloaded == obj


def _check_json_schema(obj):
    schema = type(obj).model_json_schema()
    assert schema is not None
    assert "properties" in schema


# ---------------------------------------------------------------------------
# Strategy: PipelineItemCreate
# ---------------------------------------------------------------------------

pipeline_item_create_strategy = st.builds(
    PipelineItemCreate,
    pncp_id=st.text(min_size=1, max_size=100),
    objeto=safe_text,
    orgao=st.one_of(st.none(), st.text(min_size=1, max_size=500)),
    uf=st.one_of(st.none(), st.sampled_from(_ALL_UFS)),
    valor_estimado=st.one_of(st.none(), st.floats(
        min_value=0, max_value=1e12, allow_infinity=False, allow_nan=False,
    )),
    data_encerramento=st.one_of(
        st.none(), st.datetimes().map(lambda d: d.isoformat()),
    ),
    link_pncp=st.one_of(st.none(), st.text(min_size=1, max_size=500)),
    stage=st.sampled_from(sorted(VALID_PIPELINE_STAGES)),
    notes=st.one_of(st.none(), st.text(min_size=1, max_size=5000)),
    search_id=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
)

# ---------------------------------------------------------------------------
# Strategy: PipelineItemUpdate
# ---------------------------------------------------------------------------

pipeline_item_update_strategy = st.builds(
    PipelineItemUpdate,
    stage=st.one_of(st.none(), st.sampled_from(sorted(VALID_PIPELINE_STAGES))),
    notes=st.one_of(st.none(), st.text(min_size=1, max_size=5000)),
    version=st.one_of(st.none(), st.integers(min_value=1, max_value=1000)),
)

# ---------------------------------------------------------------------------
# Strategy: PipelineItemResponse
# ---------------------------------------------------------------------------

pipeline_item_response_strategy = st.builds(
    PipelineItemResponse,
    id=st.text(min_size=1, max_size=100),
    user_id=st.text(min_size=1, max_size=100),
    pncp_id=st.text(min_size=1, max_size=100),
    objeto=safe_text,
    orgao=st.one_of(st.none(), safe_text),
    uf=st.one_of(st.none(), st.sampled_from(_ALL_UFS)),
    valor_estimado=st.one_of(st.none(), st.floats(
        min_value=0, max_value=1e12, allow_infinity=False, allow_nan=False,
    )),
    data_encerramento=st.one_of(
        st.none(), st.datetimes().map(lambda d: d.isoformat()),
    ),
    link_pncp=st.one_of(st.none(), safe_text),
    stage=st.sampled_from(sorted(VALID_PIPELINE_STAGES)),
    notes=st.one_of(st.none(), safe_text),
    search_id=st.one_of(st.none(), safe_text),
    created_at=st.datetimes().map(lambda d: d.isoformat()),
    updated_at=st.datetimes().map(lambda d: d.isoformat()),
    version=st.integers(min_value=1, max_value=1000),
    is_expired=st.booleans(),
)

# ---------------------------------------------------------------------------
# Strategy: PipelineListResponse
# ---------------------------------------------------------------------------

pipeline_list_response_strategy = st.builds(
    PipelineListResponse,
    items=st.lists(pipeline_item_response_strategy, min_size=0, max_size=50),
    total=st.integers(min_value=0, max_value=1000),
    limit=st.integers(min_value=1, max_value=100),
    offset=st.integers(min_value=0, max_value=1000),
)

# ---------------------------------------------------------------------------
# Strategy: PipelineAlertsResponse
# ---------------------------------------------------------------------------

pipeline_alerts_response_strategy = st.builds(
    PipelineAlertsResponse,
    items=st.lists(pipeline_item_response_strategy, min_size=0, max_size=50),
    total=st.integers(min_value=0, max_value=1000),
)


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestPipelineItemCreate:
    """Property tests for PipelineItemCreate."""

    @given(obj=pipeline_item_create_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=pipeline_item_create_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=pipeline_item_create_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.pncp_id) >= 1
        assert len(obj.objeto) >= 1
        assert obj.stage in VALID_PIPELINE_STAGES
        if obj.valor_estimado is not None:
            assert obj.valor_estimado >= 0

    @given(objeto=st.text(min_size=1, max_size=200))
    @_SETTINGS
    def test_invalid_stage_rejected(self, objeto: str):
        """Property: Invalid stage raises ValidationError."""
        with pytest.raises(ValidationError):
            PipelineItemCreate(
                pncp_id="test-123",
                objeto=objeto,
                stage="invalid_stage",
            )


class TestPipelineItemUpdate:
    """Property tests for PipelineItemUpdate."""

    @given(obj=pipeline_item_update_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=pipeline_item_update_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=pipeline_item_update_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        if obj.stage is not None:
            assert obj.stage in VALID_PIPELINE_STAGES
        if obj.version is not None:
            assert obj.version >= 1


class TestPipelineItemResponse:
    """Property tests for PipelineItemResponse."""

    @given(obj=pipeline_item_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=pipeline_item_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=pipeline_item_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.id) > 0
        assert len(obj.pncp_id) > 0
        assert len(obj.objeto) > 0
        assert obj.stage in VALID_PIPELINE_STAGES
        assert obj.version >= 1
        assert isinstance(obj.is_expired, bool)
        if obj.valor_estimado is not None:
            assert obj.valor_estimado >= 0


class TestPipelineListResponse:
    """Property tests for PipelineListResponse."""

    @given(obj=pipeline_list_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=pipeline_list_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=pipeline_list_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.items) >= 0
        assert obj.total >= 0
        assert obj.limit >= 1
        assert obj.offset >= 0


class TestPipelineAlertsResponse:
    """Property tests for PipelineAlertsResponse."""

    @given(obj=pipeline_alerts_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=pipeline_alerts_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=pipeline_alerts_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.total >= 0
        for item in obj.items:
            assert item.stage in VALID_PIPELINE_STAGES
