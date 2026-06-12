"""SUBINTEL-030 (#1665): Subcontracting Intelligence health/status route.

GET /v1/subcontract/health — returns the gate status so the frontend can
decide whether to render SUBINTEL sections.

Feature flag: SUBCONTRACT_INTEL_ENABLED (config/features.py)
Plan capability: allow_subcontract_intel (PlanCapabilities)
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from auth import require_auth
from quota.plan_auth import check_subcontract_intel_access

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/subcontract", tags=["subcontract"])


class SubcontractHealthResponse(BaseModel):
    """Health check response for the Subcontracting Intelligence vertical."""

    enabled: bool = Field(..., description="Global feature flag state")
    has_access: bool = Field(..., description="Current user has plan capability")
    feature_flag: str = Field(
        "SUBCONTRACT_INTEL_ENABLED",
        description="Feature flag name",
    )


@router.get("/health", response_model=SubcontractHealthResponse)
async def subcontract_health(user: dict = Depends(require_auth)):
    """Check if the Subcontracting Intelligence vertical is accessible.

    Returns the global feature flag state and whether the authenticated user
    has the ``allow_subcontract_intel`` plan capability (or is master/admin).

    Frontend uses this to decide if SUBINTEL UI sections should render.
    """
    from config.features import get_feature_flag

    flag_enabled = get_feature_flag("SUBCONTRACT_INTEL_ENABLED")
    has_access = await check_subcontract_intel_access(user)

    return SubcontractHealthResponse(
        enabled=flag_enabled,
        has_access=has_access,
    )
