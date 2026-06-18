"""Issue #1973: Admin endpoint for granular rate limit configuration.

GET /v1/admin/rate-limits — returns current rate limit configuration
for all tiers and endpoints. Requires ``admin:ops`` role.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends

from admin import require_admin_ops
from config.features import get_feature_flag
from rate_limiter import (
    _ENDPOINT_RATE_LIMITS,
    _RATE_LIMIT_EXEMPT_ENDPOINTS,
    _TIER_RPM,
)
from schemas.admin import RateLimitConfigResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get(
    "/rate-limits",
    response_model=RateLimitConfigResponse,
)
async def get_rate_limits_config(
    user: dict = Depends(require_admin_ops),
) -> RateLimitConfigResponse:
    """Return the current rate limit configuration.

    Returns all tier RPMs, per-endpoint overrides, exempt endpoints,
    and the feature flag state. Admin-only (requires ``admin:ops``).
    """
    tiers: Dict[str, int] = dict(_TIER_RPM)
    endpoints: Dict[str, Dict[str, Any]] = {
        path: dict(conf)
        for path, conf in _ENDPOINT_RATE_LIMITS.items()
    }
    exempt: list[str] = sorted(_RATE_LIMIT_EXEMPT_ENDPOINTS)
    flag_enabled: bool = get_feature_flag("RATE_LIMIT_PER_ENDPOINT_ENABLED")

    return RateLimitConfigResponse(
        tiers=tiers,
        endpoints=endpoints,
        exempt_endpoints=exempt,
        feature_flag_enabled=flag_enabled,
    )
