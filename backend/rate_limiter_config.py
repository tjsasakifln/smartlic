"""Rate limiter configuration — tier and endpoint rate limits.

Issue #1973: Granular rate limiting per endpoint and tier.
All values overridable via env vars for runtime configuration without code changes.

Tier hierarchy: anonymous (10/min) < trial (30/min) < pro (60/min) < admin (120/min)
Endpoint overrides further restrict specific paths (e.g., /buscar: trial=3/min).
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# ============================================================================
# Tier definitions (env var overridable)
# ============================================================================

RL_ANONYMOUS_PER_MIN = int(os.getenv("RL_ANONYMOUS_PER_MIN", "10"))
RL_TRIAL_PER_MIN = int(os.getenv("RL_TRIAL_PER_MIN", "30"))
RL_PRO_PER_MIN = int(os.getenv("RL_PRO_PER_MIN", "60"))
RL_ADMIN_PER_MIN = int(os.getenv("RL_ADMIN_PER_MIN", "120"))
RL_WINDOW_SECONDS = int(os.getenv("RL_WINDOW_SECONDS", "60"))

TIER_LIMITS: dict[str, tuple[int, int]] = {
    "anonymous": (RL_ANONYMOUS_PER_MIN, RL_WINDOW_SECONDS),
    "trial": (RL_TRIAL_PER_MIN, RL_WINDOW_SECONDS),
    "pro": (RL_PRO_PER_MIN, RL_WINDOW_SECONDS),
    "admin": (RL_ADMIN_PER_MIN, RL_WINDOW_SECONDS),
}

DEFAULT_TIER = "anonymous"
DEFAULT_TIER_LIMIT = TIER_LIMITS[DEFAULT_TIER]

# ============================================================================
# Endpoint-specific overrides (env var as JSON dict)
# ============================================================================
# Expected format:
#   ENDPOINT_RATE_LIMITS='{"/buscar": {"trial": 3, "pro": 10, "admin": 20}}'
# Tiers not listed in an override inherit their tier default.

_ENDPOINT_LIMITS_ENV = os.getenv("ENDPOINT_RATE_LIMITS", "")
_ENDPOINT_RATE_LIMITS: dict[str, dict[str, int]] | None = None

if _ENDPOINT_LIMITS_ENV and _ENDPOINT_LIMITS_ENV.strip():
    try:
        parsed = json.loads(_ENDPOINT_LIMITS_ENV)
        if isinstance(parsed, dict):
            _ENDPOINT_RATE_LIMITS = parsed
        else:
            logger.warning(
                "ENDPOINT_RATE_LIMITS must be a JSON object, got %s",
                type(parsed).__name__,
            )
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("Invalid ENDPOINT_RATE_LIMITS env var: %s", e)

if _ENDPOINT_RATE_LIMITS is None:
    _ENDPOINT_RATE_LIMITS = {
        "/buscar": {"trial": 3, "pro": 10, "admin": 20},
        "/v1/pipeline": {"anonymous": 10, "trial": 30, "pro": 30, "admin": 30},
    }

ENDPOINT_RATE_LIMITS: dict[str, dict[str, int]] = _ENDPOINT_RATE_LIMITS

# ============================================================================
# Exempt paths — these endpoints have no rate limit applied
# ============================================================================

RATE_LIMIT_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/health",
    "/v1/health",
    "/metrics",
)

# ============================================================================
# Helper functions
# ============================================================================


def get_tier_limit(tier: str) -> tuple[int, int]:
    """Get (max_requests, window_seconds) for a tier.

    Falls back to anonymous tier defaults if tier not found.
    """
    return TIER_LIMITS.get(tier, DEFAULT_TIER_LIMIT)


def get_endpoint_max_requests(tier: str, endpoint: str) -> int | None:
    """Get max requests for a (tier, endpoint) pair.

    Returns None if the endpoint is exempt (no rate limit applied).

    Resolution order:
    1. Endpoint-specific override for this tier (longest prefix match)
    2. Fall back to tier default
    """
    # Check exempt prefixes first
    for prefix in RATE_LIMIT_EXEMPT_PREFIXES:
        if endpoint == prefix or endpoint.startswith(prefix + "/"):
            return None

    # Check endpoint-specific overrides — sort by length desc for most specific
    sorted_prefixes = sorted(ENDPOINT_RATE_LIMITS.keys(), key=len, reverse=True)
    for path_prefix in sorted_prefixes:
        if endpoint.startswith(path_prefix):
            tier_limits = ENDPOINT_RATE_LIMITS[path_prefix]
            if tier in tier_limits:
                return tier_limits[tier]
            # Tier not in this override — fall through to tier default
            break

    # Tier default
    tier_limit, _ = get_tier_limit(tier)
    return tier_limit


def get_endpoint_window(endpoint: str) -> int:
    """Get rate limit window in seconds for an endpoint."""
    return RL_WINDOW_SECONDS


def is_exempt(endpoint: str) -> bool:
    """Check if an endpoint is exempt from rate limiting."""
    for prefix in RATE_LIMIT_EXEMPT_PREFIXES:
        if endpoint == prefix or endpoint.startswith(prefix + "/"):
            return True
    return False


def get_all_config() -> dict:
    """Return full rate limit configuration for the admin endpoint."""
    tiers = {}
    for tier in sorted(TIER_LIMITS.keys()):
        limit, window = get_tier_limit(tier)
        tiers[tier] = {
            "max_requests": limit,
            "window_seconds": window,
        }

    endpoints = {}
    for prefix, tier_limits in ENDPOINT_RATE_LIMITS.items():
        endpoints[prefix] = dict(tier_limits)

    return {
        "tiers": tiers,
        "endpoint_overrides": endpoints,
        "exempt_prefixes": list(RATE_LIMIT_EXEMPT_PREFIXES),
        "window_seconds": RL_WINDOW_SECONDS,
    }
