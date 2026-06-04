"""Tests for the Command Tier capability gates (TIER-COMMAND-003, ISSUE #1450).

Covers:
  - Non-regression: every existing plan defaults Command capabilities to False
  - Stage 1 gate: unknown flag in registry => HTTP 503 (fail-closed)
  - Stage 2 gate: feature flag OFF => HTTP 503 (fail-closed, no feature leak)
  - Stage 3 gate: capability False => HTTP 403 upsell
  - capability True => access granted
  - master/admin bypass
  - fail-closed on Supabase circuit-breaker open
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from quota import (
    PLAN_CAPABILITIES,
    requires_command_api_access,
    requires_command_multi_user,
    requires_command_executive_reports,
    requires_command_capability,
)
from supabase_client import CircuitBreakerOpenError

USER = {"id": "user-123"}

# Every plan_id shipped today -- gate must be invisible to all of them by default.
EXISTING_PLANS = [
    "free_trial",
    "consultor_agil",
    "maquina",
    "sala_guerra",
    "smartlic_pro",
    "founding_member",
    "consultoria",
    "free",
    "master",
]

# All Command capability fields
_COMMAND_CAPABILITY_KEYS = [
    "allow_command_api_access",
    "allow_command_multi_user",
    "allow_command_executive_reports",
]


class TestNonRegression:
    """Adding the capabilities must not change any existing plan's behaviour."""

    @pytest.mark.parametrize("plan_id", EXISTING_PLANS)
    @pytest.mark.parametrize("cap_key", _COMMAND_CAPABILITY_KEYS)
    def test_existing_plan_defaults_command_capabilities_false(self, plan_id, cap_key):
        assert plan_id in PLAN_CAPABILITIES
        assert PLAN_CAPABILITIES[plan_id][cap_key] is False

    @pytest.mark.parametrize("plan_id", EXISTING_PLANS)
    def test_existing_plan_keeps_legacy_capabilities(self, plan_id):
        """The new keys are purely additive -- legacy keys remain present."""
        caps = PLAN_CAPABILITIES[plan_id]
        for legacy_key in (
            "max_history_days",
            "allow_excel",
            "allow_pipeline",
            "max_requests_per_month",
            "priority",
        ):
            assert legacy_key in caps


def _mock_quota(allow: bool, plan_id: str = "free_trial"):
    return SimpleNamespace(
        capabilities={
            "allow_command_api_access": allow,
            "allow_command_multi_user": allow,
            "allow_command_executive_reports": allow,
        },
        plan_id=plan_id,
        allowed=True,
    )


def _mock_quota_plan(plan_id: str):
    """Mock quota for a specific plan with command capabilities matching it."""
    caps = PLAN_CAPABILITIES.get(plan_id, {})
    return SimpleNamespace(
        capabilities={
            "allow_command_api_access": caps.get("allow_command_api_access", False),
            "allow_command_multi_user": caps.get("allow_command_multi_user", False),
            "allow_command_executive_reports": caps.get("allow_command_executive_reports", False),
        },
        plan_id=plan_id,
        allowed=True,
    )


@pytest.mark.asyncio
class TestCommandCapabilityGate:
    """Test the generic requires_command_capability function."""

    async def test_unknown_flag_returns_503(self):
        """Fail-closed: flag not in registry => 503."""
        with patch("config.features._FEATURE_FLAG_REGISTRY", {}), \
             patch("config.features.get_feature_flag", return_value=True):
            with pytest.raises(HTTPException) as exc:
                await requires_command_capability(USER, "COMMAND_API_ACCESS")
        assert exc.value.status_code == 503

    async def test_flag_off_returns_503(self):
        """Stage 1: flag off => 503 (fail-closed, no feature leak)."""
        with patch("config.features.get_feature_flag", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await requires_command_capability(USER, "COMMAND_API_ACCESS")
        assert exc.value.status_code == 503

    async def test_capability_false_returns_403(self):
        """Stage 2: enabled but plan lacks capability => upsell 403."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(return_value=_mock_quota(False))), \
             patch("quota.plan_auth.track_funnel_event"):
            with pytest.raises(HTTPException) as exc:
                await requires_command_capability(USER, "COMMAND_API_ACCESS")
        assert exc.value.status_code == 403
        assert exc.value.detail["error_code"] == "command_api_access_not_available"

    async def test_capability_true_passes(self):
        """Plan with the capability is granted access (returns the user)."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(return_value=_mock_quota(True, "smartlic_command"))):
            result = await requires_command_capability(USER, "COMMAND_API_ACCESS")
        assert result == USER

    async def test_master_bypasses_capability_gate(self):
        """Master/admin always passes even when the plan capability is False."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=True)):
            result = await requires_command_capability(USER, "COMMAND_API_ACCESS")
        assert result == USER

    async def test_circuit_breaker_open_fails_closed(self):
        """Premium gate must NOT open when Supabase circuit breaker is open."""
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(side_effect=CircuitBreakerOpenError("cb open"))):
            with pytest.raises(HTTPException) as exc:
                await requires_command_capability(USER, "COMMAND_API_ACCESS")
        assert exc.value.status_code == 503


@pytest.mark.asyncio
class TestCommandApiAccessGate:
    """Test the specific requires_command_api_access function."""

    async def test_flag_off_returns_503(self):
        with patch("config.features.get_feature_flag", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await requires_command_api_access(USER)
        assert exc.value.status_code == 503

    async def test_flag_on_capability_false_returns_403(self):
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(return_value=_mock_quota(False))), \
             patch("quota.plan_auth.track_funnel_event"):
            with pytest.raises(HTTPException) as exc:
                await requires_command_api_access(USER)
        assert exc.value.status_code == 403
        assert exc.value.detail["error_code"] == "command_api_access_not_available"

    async def test_flag_on_capability_true_passes(self):
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(return_value=_mock_quota(True, "smartlic_command"))):
            result = await requires_command_api_access(USER)
        assert result == USER


@pytest.mark.asyncio
class TestCommandMultiUserGate:
    """Test the specific requires_command_multi_user function."""

    async def test_flag_off_returns_503(self):
        with patch("config.features.get_feature_flag", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await requires_command_multi_user(USER)
        assert exc.value.status_code == 503

    async def test_flag_on_capability_false_returns_403(self):
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(return_value=_mock_quota(False))), \
             patch("quota.plan_auth.track_funnel_event"):
            with pytest.raises(HTTPException) as exc:
                await requires_command_multi_user(USER)
        assert exc.value.status_code == 403
        assert exc.value.detail["error_code"] == "command_multi_user_not_available"

    async def test_flag_on_capability_true_passes(self):
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(return_value=_mock_quota(True, "smartlic_command"))):
            result = await requires_command_multi_user(USER)
        assert result == USER


@pytest.mark.asyncio
class TestCommandExecutiveReportsGate:
    """Test the specific requires_command_executive_reports function."""

    async def test_flag_off_returns_503(self):
        with patch("config.features.get_feature_flag", return_value=False):
            with pytest.raises(HTTPException) as exc:
                await requires_command_executive_reports(USER)
        assert exc.value.status_code == 503

    async def test_flag_on_capability_false_returns_403(self):
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(return_value=_mock_quota(False))), \
             patch("quota.plan_auth.track_funnel_event"):
            with pytest.raises(HTTPException) as exc:
                await requires_command_executive_reports(USER)
        assert exc.value.status_code == 403
        assert exc.value.detail["error_code"] == "command_executive_reports_not_available"

    async def test_flag_on_capability_true_passes(self):
        with patch("config.features.get_feature_flag", return_value=True), \
             patch("authorization.has_master_access", new=AsyncMock(return_value=False)), \
             patch("quota.plan_enforcement.check_quota",
                   MagicMock(return_value=_mock_quota(True, "smartlic_command"))):
            result = await requires_command_executive_reports(USER)
        assert result == USER
