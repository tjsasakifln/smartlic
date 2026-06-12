"""NETINT-008: Pipeline metrics + observability endpoints.

Provides a health/status endpoint for the network intelligence pipeline
that exposes aggregated metrics (24h event count, opt-in rate, etc.).

Endpoint:
  GET /v1/network-intel/health — Pipeline dashboard
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from services.network_metrics import get_network_health

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/network-intel", tags=["network-intel"])


@router.get("/health")
async def network_intel_health():
    """Get health status of the network intelligence pipeline.

    Returns aggregated metrics: 24h event counts, opt-in rate,
    table size, and cleanup job metadata.

    No authentication required — endpoint exposes only anonymized
    aggregated data. No PII.
    """
    result = await get_network_health()
    return result
