"""Tests for rate_limiter_config — Issue #1973 granular rate limiting.

Tests cover:
- Tier limit resolution
- Endpoint-specific override resolution
- Exempt path detection
- Env var override behavior
- Full config export
"""

import os
from unittest.mock import patch

import pytest
from rate_limiter_config import (
    get_tier_limit,
    get_endpoint_max_requests,
    get_endpoint_window,
    is_exempt,
    get_all_config,
    RL_WINDOW_SECONDS,
)


class TestTierLimits:
    """Test tier limit resolution."""

    def test_default_tier_limits(self):
        """Should return correct limits for each tier."""
        assert get_tier_limit("anonymous") == (10, 60)
        assert get_tier_limit("trial") == (30, 60)
        assert get_tier_limit("pro") == (60, 60)
        assert get_tier_limit("admin") == (120, 60)

    def test_unknown_tier_falls_back_to_anonymous(self):
        """Should fall back to anonymous for unknown tier."""
        limit, window = get_tier_limit("nonexistent")
        assert limit == 10
        assert window == 60

    def test_tier_limits_env_vars_readable(self):
        """Env vars used for tier limits should have sensible defaults."""
        # Verify the constants were loaded from env vars with defaults
        import rate_limiter_config
        assert rate_limiter_config.RL_ANONYMOUS_PER_MIN >= 1
        assert rate_limiter_config.RL_TRIAL_PER_MIN >= 1
        assert rate_limiter_config.RL_PRO_PER_MIN >= 1
        assert rate_limiter_config.RL_ADMIN_PER_MIN >= 1
        assert rate_limiter_config.RL_WINDOW_SECONDS >= 1

    @patch.dict(os.environ, {"RL_PRO_PER_MIN": "100"})
    def test_tier_limits_env_override_pro(self):
        """Should respect RL_PRO_PER_MIN env var."""
        import importlib
        import rate_limiter_config
        importlib.reload(rate_limiter_config)

        assert rate_limiter_config.RL_PRO_PER_MIN == 100
        # Restore
        importlib.reload(rate_limiter_config)


class TestEndpointOverrides:
    """Test endpoint-specific rate limit resolution."""

    def test_buscar_endpoint_overrides(self):
        """Should return correct limits for /buscar by tier."""
        assert get_endpoint_max_requests("trial", "/buscar") == 3
        assert get_endpoint_max_requests("pro", "/buscar") == 10
        assert get_endpoint_max_requests("admin", "/buscar") == 20

    def test_buscar_anonymous_falls_back_to_tier_default(self):
        """Should fall back to tier default when tier not in endpoint override."""
        limit = get_endpoint_max_requests("anonymous", "/buscar")
        assert limit == 10  # anonymous tier default

    def test_pipeline_endpoint_overrides(self):
        """Should return correct limits for /v1/pipeline."""
        assert get_endpoint_max_requests("anonymous", "/v1/pipeline") == 10
        assert get_endpoint_max_requests("trial", "/v1/pipeline") == 30
        assert get_endpoint_max_requests("pro", "/v1/pipeline") == 30
        assert get_endpoint_max_requests("admin", "/v1/pipeline") == 30

    def test_unconfigured_endpoint_uses_tier_default(self):
        """Should return tier default for endpoints without specific override."""
        limit = get_endpoint_max_requests("admin", "/some-other-endpoint")
        assert limit == 120

    def test_longest_prefix_match(self):
        """Should use longest matching prefix for endpoint resolution."""
        limit = get_endpoint_max_requests("trial", "/buscar/custom/path")
        assert limit == 3  # /buscar prefix matches


class TestExemptPaths:
    """Test exempt path detection."""

    def test_health_is_exempt(self):
        """Should treat /health as exempt."""
        assert get_endpoint_max_requests("anonymous", "/health") is None

    def test_v1_health_is_exempt(self):
        """Should treat /v1/health as exempt."""
        assert get_endpoint_max_requests("trial", "/v1/health") is None

    def test_v1_health_live_is_exempt(self):
        """Should treat /v1/health/live as exempt."""
        assert get_endpoint_max_requests("pro", "/v1/health/live") is None

    def test_metrics_is_exempt(self):
        """Should treat /metrics as exempt."""
        assert get_endpoint_max_requests("admin", "/metrics") is None

    def test_buscar_is_not_exempt(self):
        """Should NOT treat /buscar as exempt."""
        result = get_endpoint_max_requests("pro", "/buscar")
        assert result == 10


class TestIsExempt:
    """Test the is_exempt helper."""

    def test_health_is_exempt(self):
        """is_exempt should return True for /health."""
        assert is_exempt("/health") is True
        assert is_exempt("/health/live") is True

    def test_buscar_is_not_exempt(self):
        """is_exempt should return False for /buscar."""
        assert is_exempt("/buscar") is False


class TestGetEndpointWindow:
    """Test window resolution."""

    def test_returns_default_window(self):
        """Should return default window for any endpoint."""
        assert get_endpoint_window("/buscar") == RL_WINDOW_SECONDS
        assert get_endpoint_window("/v1/pipeline") == RL_WINDOW_SECONDS


class TestGetAllConfig:
    """Test full config export."""

    def test_get_all_config_returns_all_tiers(self):
        """Should include all defined tiers."""
        config = get_all_config()
        assert set(config["tiers"].keys()) == {"anonymous", "trial", "pro", "admin"}

    def test_get_all_config_includes_endpoints(self):
        """Should include endpoint overrides."""
        config = get_all_config()
        assert "/buscar" in config["endpoint_overrides"]

    def test_get_all_config_includes_exempt(self):
        """Should include exempt prefixes."""
        config = get_all_config()
        assert "/health" in config["exempt_prefixes"]

    def test_get_all_config_includes_window(self):
        """Should include window_seconds."""
        config = get_all_config()
        assert config["window_seconds"] == RL_WINDOW_SECONDS
