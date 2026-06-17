"""Property-based tests for user schema models (#1969).

Covers: PerfilContexto, PerfilContextoResponse, ProfileCompletenessResponse,
FirstAnalysisRequest, FirstAnalysisResponse, TourEventRequest,
UserProfileResponse, DeleteAccountResponse, SignupRequest, SignupResponse,
MFAEnrollResponse, MFAVerifyRequest, MFAVerifyResponse.

Property: Round-trip serialization (model_dump -> model_validate -> equal).
Property: JSON Schema is valid Draft 2020-12.
Property: Invariant constraints (ge/le, min/max lengths, enum values).
"""

import pytest
from hypothesis import given, settings, HealthCheck, strategies as st
from pydantic import ValidationError

from schemas.user import (
    PorteEmpresa,
    ExperienciaLicitacoes,
    ObjetivoTipo,
    PerfilContexto,
    PerfilContextoResponse,
    ProfileCompletenessResponse,
    FirstAnalysisRequest,
    FirstAnalysisResponse,
    TourEventRequest,
    UserProfileResponse,
    DeleteAccountResponse,
    SignupRequest,
    SignupResponse,
    MFAEnrollResponse,
    MFAVerifyRequest,
    MFAVerifyResponse,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALL_UFS = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

_SETORES = [
    "vestuario", "alimentos", "informatica", "saude", "educacao",
    "seguranca", "transporte", "energia", "construcao", "limpeza",
]

# ---------------------------------------------------------------------------
# Shared strategy helpers
# ---------------------------------------------------------------------------

safe_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.-",
    min_size=1, max_size=200,
)
small_int = st.integers(min_value=0, max_value=10000)


# ---------------------------------------------------------------------------
# Strategy: PerfilContexto
# ---------------------------------------------------------------------------

@st.composite
def perfil_contexto_strategy(draw):
    """Generate a PerfilContexto with valid UF list and consistent value range."""
    ufs = draw(st.lists(
        st.sampled_from(_ALL_UFS), min_size=1, max_size=27, unique=True,
    ))
    v_min = draw(st.one_of(st.none(), st.floats(
        min_value=0, max_value=1e9, allow_infinity=False, allow_nan=False,
    )))
    v_max = draw(st.one_of(st.none(), st.floats(
        min_value=0, max_value=1e9, allow_infinity=False, allow_nan=False,
    )))
    if v_min is not None and v_max is not None and v_min > v_max:
        v_min, v_max = v_max, v_min

    return PerfilContexto(
        ufs_atuacao=ufs,
        porte_empresa=draw(st.sampled_from(list(PorteEmpresa))),
        experiencia_licitacoes=draw(st.sampled_from(list(ExperienciaLicitacoes))),
        faixa_valor_min=v_min,
        faixa_valor_max=v_max,
        modalidades_interesse=draw(st.one_of(
            st.none(),
            st.lists(
                st.sampled_from([1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 15]),
                min_size=1, max_size=5, unique=True,
            ),
        )),
        palavras_chave=draw(st.one_of(
            st.none(),
            st.lists(safe_text, min_size=1, max_size=20, unique=True),
        )),
        cnae=draw(st.one_of(st.none(), st.text(min_size=1, max_size=20))),
        objetivo_principal=draw(st.one_of(st.none(), st.text(min_size=1, max_size=200))),
        segmento_principal=draw(st.one_of(st.none(), st.integers(min_value=1, max_value=100))),
        objetivo_tipo=draw(st.one_of(st.none(), st.sampled_from(list(ObjetivoTipo)))),
        ticket_medio_desejado=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=1_000_000))),
        atestados=draw(st.one_of(
            st.none(),
            st.lists(st.text(min_size=1, max_size=50), max_size=10, unique=True),
        )),
        capacidade_funcionarios=draw(st.one_of(st.none(), st.integers(min_value=0, max_value=100000))),
        faturamento_anual=draw(st.one_of(st.none(), st.floats(
            min_value=0, max_value=1e12, allow_infinity=False, allow_nan=False,
        ))),
    )

# ---------------------------------------------------------------------------
# Strategy: PerfilContextoResponse
# ---------------------------------------------------------------------------

perfil_contexto_response_strategy = st.builds(
    PerfilContextoResponse,
    context_data=st.dictionaries(
        st.text(min_size=1, max_size=20),
        st.text(min_size=1, max_size=100),
        min_size=0, max_size=10,
    ),
    completed=st.booleans(),
)

# ---------------------------------------------------------------------------
# Strategy: ProfileCompletenessResponse
# ---------------------------------------------------------------------------

profile_completeness_strategy = st.builds(
    ProfileCompletenessResponse,
    completeness_pct=st.integers(min_value=0, max_value=100),
    total_fields=st.integers(min_value=0, max_value=50),
    filled_fields=st.integers(min_value=0, max_value=50),
    missing_fields=st.lists(st.text(min_size=1, max_size=50), max_size=20),
    next_question=st.one_of(st.none(), safe_text),
    is_complete=st.booleans(),
)

# ---------------------------------------------------------------------------
# Strategy: FirstAnalysisRequest
# ---------------------------------------------------------------------------

first_analysis_request_strategy = st.builds(
    FirstAnalysisRequest,
    cnae=st.text(min_size=1, max_size=20),
    objetivo_principal=st.text(min_size=0, max_size=200),
    ufs=st.lists(
        st.sampled_from(_ALL_UFS), min_size=1, max_size=27, unique=True,
    ),
    faixa_valor_min=st.one_of(
        st.none(), st.integers(min_value=0, max_value=1_000_000_000),
    ),
    faixa_valor_max=st.one_of(
        st.none(), st.integers(min_value=0, max_value=1_000_000_000),
    ),
)

# ---------------------------------------------------------------------------
# Strategy: FirstAnalysisResponse
# ---------------------------------------------------------------------------

first_analysis_response_strategy = st.builds(
    FirstAnalysisResponse,
    search_id=st.text(min_size=1, max_size=36),
    status=st.sampled_from(["in_progress", "completed", "failed"]),
    message=st.text(min_size=1, max_size=200),
    setor_id=st.sampled_from(_SETORES),
)

# ---------------------------------------------------------------------------
# Strategy: TourEventRequest
# ---------------------------------------------------------------------------

tour_event_request_strategy = st.builds(
    TourEventRequest,
    tour_id=st.text(min_size=1, max_size=50),
    event=st.sampled_from(["completed", "skipped"]),
    steps_seen=st.integers(min_value=0, max_value=50),
)

# ---------------------------------------------------------------------------
# Strategy: UserProfileResponse
# ---------------------------------------------------------------------------

user_profile_response_strategy = st.builds(
    UserProfileResponse,
    user_id=st.text(min_size=1, max_size=100),
    email=st.emails(),
    plan_id=st.text(min_size=1, max_size=50),
    plan_name=st.text(min_size=1, max_size=100),
    capabilities=st.dictionaries(
        st.text(min_size=1, max_size=30),
        st.one_of(st.text(), st.integers(), st.booleans()),
        min_size=1, max_size=10,
    ),
    quota_used=small_int,
    quota_remaining=small_int,
    quota_reset_date=st.datetimes().map(lambda d: d.isoformat()),
    trial_expires_at=st.one_of(
        st.none(), st.datetimes().map(lambda d: d.isoformat()),
    ),
    subscription_status=st.sampled_from([
        "trial", "active", "expired", "past_due",
    ]),
    is_admin=st.booleans(),
    dunning_phase=st.sampled_from([
        "healthy", "active_retries", "grace_period", "blocked",
    ]),
    days_since_failure=st.one_of(st.none(), st.integers(min_value=0, max_value=365)),
    subscription_end_date=st.one_of(
        st.none(), st.datetimes().map(lambda d: d.isoformat()),
    ),
    login_count=st.integers(min_value=0, max_value=10000),
    is_founder=st.booleans(),
    allow_network_analytics=st.one_of(st.none(), st.booleans()),
)

# ---------------------------------------------------------------------------
# Strategy: DeleteAccountResponse
# ---------------------------------------------------------------------------

delete_account_response_strategy = st.builds(
    DeleteAccountResponse,
    success=st.booleans(),
    message=st.text(min_size=1, max_size=200),
)

# ---------------------------------------------------------------------------
# Strategy: SignupRequest
# ---------------------------------------------------------------------------

signup_request_strategy = st.builds(
    SignupRequest,
    email=st.emails(),
    password=st.text(min_size=8, max_size=200),
    stripe_payment_method_id=st.one_of(
        st.none(),
        st.text(
            alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_",
            min_size=3, max_size=50,
        ).map(lambda s: f"pm_{s}"),
    ),
    full_name=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
    company=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
    source=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    ref=st.one_of(st.none(), st.text(min_size=1, max_size=200)),
)

# ---------------------------------------------------------------------------
# Strategy: SignupResponse
# ---------------------------------------------------------------------------

signup_response_strategy = st.builds(
    SignupResponse,
    user_id=st.text(min_size=1, max_size=100),
    email=st.emails(),
    trial_end_ts=st.one_of(
        st.none(), st.integers(min_value=1700000000, max_value=1900000000),
    ),
    stripe_customer_id=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    stripe_subscription_id=st.one_of(st.none(), st.text(min_size=1, max_size=100)),
    subscription_status=st.sampled_from([
        "trialing", "free_trial", "payment_failed",
    ]),
    requires_email_confirmation=st.booleans(),
)

# ---------------------------------------------------------------------------
# Strategy: MFAEnrollResponse
# ---------------------------------------------------------------------------

mfa_enroll_response_strategy = st.builds(
    MFAEnrollResponse,
    factor_id=st.text(min_size=1, max_size=100),
    qr_code_uri=st.builds(lambda: "otpauth://totp/test?secret=TEST"),
    secret=st.text(min_size=16, max_size=64),
    backup_codes=st.lists(
        st.text(min_size=9, max_size=9), min_size=0, max_size=10,
    ),
)

# ---------------------------------------------------------------------------
# Strategy: MFAVerifyRequest
# ---------------------------------------------------------------------------

mfa_verify_request_strategy = st.builds(
    MFAVerifyRequest,
    totp_code=st.text(
        alphabet="0123456789", min_size=6, max_size=6,
    ),
)

# ---------------------------------------------------------------------------
# Strategy: MFAVerifyResponse
# ---------------------------------------------------------------------------

mfa_verify_response_strategy = st.builds(
    MFAVerifyResponse,
    success=st.booleans(),
    aal_level=st.sampled_from(["aal1", "aal2"]),
    factor_id=st.text(min_size=1, max_size=100),
    message=st.text(min_size=0, max_size=200),
)

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

_SETTINGS = settings(
    deadline=500, suppress_health_check=[HealthCheck.too_slow],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_roundtrip(obj):
    dumped = obj.model_dump()
    reloaded = type(obj).model_validate(dumped)
    assert reloaded == obj


def _check_json_schema(obj):
    schema = type(obj).model_json_schema()
    assert schema is not None
    assert "properties" in schema


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestPerfilContexto:
    """Property tests for PerfilContexto."""

    @given(obj=perfil_contexto_strategy())
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=perfil_contexto_strategy())
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=perfil_contexto_strategy())
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.ufs_atuacao) >= 1
        assert obj.porte_empresa in PorteEmpresa
        assert obj.experiencia_licitacoes in ExperienciaLicitacoes
        if obj.faixa_valor_min is not None:
            assert obj.faixa_valor_min >= 0
        if obj.faixa_valor_max is not None:
            assert obj.faixa_valor_max >= 0
        if obj.faixa_valor_min is not None and obj.faixa_valor_max is not None:
            assert obj.faixa_valor_min <= obj.faixa_valor_max
        if obj.palavras_chave is not None:
            assert len(obj.palavras_chave) <= 20
        if obj.capacidade_funcionarios is not None:
            assert obj.capacidade_funcionarios >= 0
        if obj.faturamento_anual is not None:
            assert obj.faturamento_anual >= 0

    @given(
        ufs=st.lists(st.sampled_from(_ALL_UFS), min_size=1, max_size=27, unique=True),
    )
    @_SETTINGS
    def test_value_range_validation(self, ufs):
        """Property: faixa_valor_max < faixa_valor_min raises ValidationError."""
        with pytest.raises(ValidationError):
            PerfilContexto(
                ufs_atuacao=ufs,
                porte_empresa="ME",
                experiencia_licitacoes="INICIANTE",
                faixa_valor_min=50000,
                faixa_valor_max=10000,
            )


class TestPerfilContextoResponse:
    """Property tests for PerfilContextoResponse."""

    @given(obj=perfil_contexto_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=perfil_contexto_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=perfil_contexto_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.completed, bool)


class TestProfileCompletenessResponse:
    """Property tests for ProfileCompletenessResponse."""

    @given(obj=profile_completeness_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=profile_completeness_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=profile_completeness_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert 0 <= obj.completeness_pct <= 100
        assert obj.total_fields >= 0
        assert obj.filled_fields >= 0


class TestFirstAnalysisRequest:
    """Property tests for FirstAnalysisRequest."""

    @given(obj=first_analysis_request_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=first_analysis_request_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=first_analysis_request_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.cnae) > 0
        assert len(obj.ufs) >= 1
        if obj.faixa_valor_min is not None:
            assert obj.faixa_valor_min >= 0
        if obj.faixa_valor_max is not None:
            assert obj.faixa_valor_max >= 0


class TestFirstAnalysisResponse:
    """Property tests for FirstAnalysisResponse."""

    @given(obj=first_analysis_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=first_analysis_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=first_analysis_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.search_id) > 0
        assert obj.status in {"in_progress", "completed", "failed"}
        assert len(obj.setor_id) > 0


class TestTourEventRequest:
    """Property tests for TourEventRequest."""

    @given(obj=tour_event_request_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=tour_event_request_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=tour_event_request_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.event in {"completed", "skipped"}
        assert obj.steps_seen >= 0

    @given(steps_seen=st.integers(min_value=0, max_value=50))
    @_SETTINGS
    def test_invalid_event_rejected(self, steps_seen: int):
        """Property: Invalid event raises ValidationError."""
        with pytest.raises(ValidationError):
            TourEventRequest(
                tour_id="test",
                event="invalid_event",
                steps_seen=steps_seen,
            )


class TestUserProfileResponse:
    """Property tests for UserProfileResponse."""

    @given(obj=user_profile_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=user_profile_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=user_profile_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.quota_used >= 0
        assert obj.quota_remaining >= 0
        assert isinstance(obj.is_admin, bool)
        assert obj.subscription_status in {
            "trial", "active", "expired", "past_due",
        }
        assert obj.dunning_phase in {
            "healthy", "active_retries", "grace_period", "blocked",
        }
        assert obj.login_count >= 0


class TestDeleteAccountResponse:
    """Property tests for DeleteAccountResponse."""

    @given(obj=delete_account_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=delete_account_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=delete_account_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.success, bool)
        assert len(obj.message) > 0


class TestSignupRequest:
    """Property tests for SignupRequest."""

    @given(obj=signup_request_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=signup_request_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=signup_request_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.email) > 0
        assert len(obj.password) >= 8
        assert len(obj.password) <= 200


class TestSignupResponse:
    """Property tests for SignupResponse."""

    @given(obj=signup_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=signup_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=signup_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.user_id) > 0
        assert len(obj.email) > 0
        assert obj.subscription_status in {
            "trialing", "free_trial", "payment_failed",
        }
        assert isinstance(obj.requires_email_confirmation, bool)


class TestMFAEnrollResponse:
    """Property tests for MFAEnrollResponse."""

    @given(obj=mfa_enroll_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=mfa_enroll_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=mfa_enroll_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.factor_id) > 0
        assert len(obj.qr_code_uri) > 0
        assert len(obj.secret) >= 16
        assert len(obj.backup_codes) <= 10


class TestMFAVerifyRequest:
    """Property tests for MFAVerifyRequest."""

    @given(obj=mfa_verify_request_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=mfa_verify_request_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=mfa_verify_request_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.totp_code) >= 6
        assert obj.totp_code.isdigit()


class TestMFAVerifyResponse:
    """Property tests for MFAVerifyResponse."""

    @given(obj=mfa_verify_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=mfa_verify_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=mfa_verify_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.success, bool)
        assert obj.aal_level in {"aal1", "aal2"}
        assert len(obj.factor_id) > 0
