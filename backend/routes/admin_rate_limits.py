"""Issue #1973: Admin endpoint for granular rate limit configuration.

Allows administrators to view the current rate limit configuration
(tiers, endpoint overrides, exempt prefixes, feature flag status).
"""

import logging

from fastapi import APIRouter, Depends
from admin import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/rate-limits")
async def get_rate_limits_config(
    admin: dict = Depends(require_admin),
):
    """Return the current granular rate limit configuration.

    Includes tier definitions, endpoint-specific overrides, exempt prefixes,
    window size, and whether the granular rate limiter feature is enabled.

    Requires admin authentication.
    """
    from config import get_feature_flag

    feature_enabled = get_feature_flag("RATE_LIMIT_PER_ENDPOINT_ENABLED")

    try:
        from rate_limiter_config import get_all_config
        config = get_all_config()
    except ImportError:
        # Fallback when granular config module is not available
        config = {
            "tiers": {
                "anonymous": {"max_requests": 10, "window_seconds": 60},
                "trial": {"max_requests": 30, "window_seconds": 60},
                "pro": {"max_requests": 60, "window_seconds": 60},
                "admin": {"max_requests": 120, "window_seconds": 60},
            },
            "endpoint_overrides": {},
            "exempt_prefixes": [],
            "window_seconds": 60,
        }

    config["feature_enabled"] = feature_enabled

    log_admin_action(
        logger,
        admin_id=admin["id"],
        action="view-rate-limits",
        target_user_id=admin["id"],
        details={},
    )

    return config


def log_admin_action(_logger, admin_id: str, action: str, target_user_id: str, details: dict) -> None:
    """Minimal admin action logger to avoid circular imports with admin.py.

    Logs admin actions in a consistent format matching the pattern from admin.py.
    """
    user_id_part = admin_id[:8] if admin_id else "?"
    target_part = target_user_id[:8] if target_user_id else "?"
    _logger.info(
        "Admin action: admin=%s action=%s target=%s details=%s",
        user_id_part,
        action,
        target_part,
        details,
    )
