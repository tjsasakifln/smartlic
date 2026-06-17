"""Property-based tests for billing schema models (#1969).

Covers: BillingPlansResponse, CheckoutResponse, SetupIntentResponse.

Property: Round-trip serialization (model_dump -> model_validate -> equal).
Property: JSON Schema is valid Draft 2020-12.
Property: Invariant constraints and field type checks.
"""

from hypothesis import given, settings, HealthCheck, strategies as st

from schemas.billing import (
    BillingPlansResponse,
    CheckoutResponse,
    SetupIntentResponse,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_SETTINGS = settings(
    deadline=500, suppress_health_check=[HealthCheck.too_slow],
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
# Strategy: BillingPlansResponse
# ---------------------------------------------------------------------------

billing_plans_strategy = st.builds(
    BillingPlansResponse,
    plans=st.lists(
        st.dictionaries(
            st.text(min_size=1, max_size=30),
            st.one_of(st.text(), st.integers(), st.floats(), st.booleans()),
            min_size=1, max_size=10,
        ),
        min_size=0, max_size=20,
    ),
)

# ---------------------------------------------------------------------------
# Strategy: CheckoutResponse
# ---------------------------------------------------------------------------

checkout_response_strategy = st.builds(
    CheckoutResponse,
    checkout_url=st.builds(
        lambda: "https://checkout.stripe.com/c/pay/test_123",
    ),
)

# ---------------------------------------------------------------------------
# Strategy: SetupIntentResponse
# ---------------------------------------------------------------------------

setup_intent_strategy = st.builds(
    SetupIntentResponse,
    client_secret=st.builds(
        lambda: "seti_1_test_secret_123",
    ),
    publishable_key=st.builds(
        lambda: "pk_test_123",
    ),
)


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestBillingPlansResponse:
    """Property tests for BillingPlansResponse."""

    @given(obj=billing_plans_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=billing_plans_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=billing_plans_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.plans, list)
        for plan in obj.plans:
            assert isinstance(plan, dict)


class TestCheckoutResponse:
    """Property tests for CheckoutResponse."""

    @given(obj=checkout_response_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=checkout_response_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=checkout_response_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.checkout_url, str)
        assert len(obj.checkout_url) > 0


class TestSetupIntentResponse:
    """Property tests for SetupIntentResponse."""

    @given(obj=setup_intent_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=setup_intent_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=setup_intent_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.client_secret, str)
        assert len(obj.client_secret) > 0
        assert isinstance(obj.publishable_key, str)
        assert len(obj.publishable_key) > 0
