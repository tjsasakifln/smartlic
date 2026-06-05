"""TIER-COMMAND-003: Feature flag gate for Command tier capabilities.

Each Command capability is gated behind a feature flag that must be
explicitly enabled. All flags default to False (fail-closed).

Usage:
    from command_feature_gate import check_command_capability

    if not check_command_capability("allow_command_api_access", user_plan):
        raise HTTPException(status_code=503, detail="Feature not available")
"""

import logging
from typing import Optional

from config.features import get_feature_flag
from quota.quota_core import get_plan_capabilities

logger = logging.getLogger(__name__)

# Map PlanCapabilities keys to feature flag names
CAPABILITY_FLAG_MAP: dict[str, str] = {
    "allow_command_api_access": "COMMAND_API_ACCESS",
    "allow_command_multi_user": "COMMAND_MULTI_USER",
    "allow_command_executive_reports": "COMMAND_EXECUTIVE_REPORTS",
    "allow_command_regional_intel": "COMMAND_REGIONAL_INTEL",
    "allow_command_workspace_advanced": "COMMAND_WORKSPACE_ADVANCED",
    "allow_command_data_export": "COMMAND_DATA_EXPORT",
    "allow_command_custom_alerts": "COMMAND_CUSTOM_ALERTS",
}


def check_command_capability(
    capability: str,
    user_plan: Optional[str] = None,
    user_id: Optional[str] = None,
) -> bool:
    """Check if a Command capability is enabled for the user.

    Gate order:
    1. Plan must have the capability enabled (plan-level gate)
    2. Feature flag must be enabled (global kill-switch, fail-closed)

    Returns True if both gates pass.
    """
    flag_name = CAPABILITY_FLAG_MAP.get(capability)
    if not flag_name:
        logger.warning(f"Unknown Command capability: {capability}")
        return False

    # Plan-level gate
    if user_plan:
        caps = get_plan_capabilities().get(user_plan)
        if not caps or not caps.get(capability):
            logger.debug(
                f"Command capability '{capability}' not in plan '{user_plan}'"
            )
            return False

    # Feature flag gate (fail-closed: default False)
    if not get_feature_flag(flag_name):
        logger.info(
            f"Command feature flag '{flag_name}' is disabled "
            f"(user={user_id[:8] if user_id else 'unknown'}...)"
        )
        return False

    return True
