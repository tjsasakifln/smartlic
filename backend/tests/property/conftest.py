"""Hypothesis profile configuration for property-based tests (#1920).

Profiles:
  - ci:     100 examples, suppresses too_slow health check (CI pipeline)
  - dev:    10  examples, fast feedback during development (default)
  - ci-full: 200 examples, thorough run (weekly/ad-hoc)

Usage:
    # Default (dev) — 10 examples
    pytest tests/property/

    # CI profile — 100 examples
    pytest --hypothesis-profile=ci tests/property/

    # Full profile — 200 examples
    pytest --hypothesis-profile=ci-full tests/property/
"""

from hypothesis import HealthCheck, settings

settings.register_profile(
    "ci",
    max_examples=100,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)
settings.register_profile(
    "dev",
    max_examples=10,
)
settings.register_profile(
    "ci-full",
    max_examples=200,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)

# Default: fast local development
settings.load_profile("dev")
