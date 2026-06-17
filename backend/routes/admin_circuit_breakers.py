"""Issue #1919 — Circuit breaker admin endpoint.

GET /v1/admin/circuit-breakers — Returns real-time state of all circuit
breakers (PNCP, PCP, ComprasGov, BrasilAPI, IBGE). Admin-only.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends

from admin import require_admin_ops
from clients.pncp.circuit_breaker import get_all_circuit_breaker_states

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/admin", tags=["admin", "circuit-breakers"])


@router.get("/circuit-breakers", response_model=dict)
async def get_circuit_breakers(
    user: dict = Depends(require_admin_ops),
) -> dict[str, Any]:
    """Return real-time state of all circuit breakers.

    Returns a dict keyed by source name with per-CB state including
    degraded status, failure count, open duration, and configuration.
    """
    try:
        states = await get_all_circuit_breaker_states()
        return {"circuit_breakers": states}
    except Exception as exc:
        logger.warning("GET /v1/admin/circuit-breakers failed: %s", exc)
        return {"circuit_breakers": {}, "error": str(exc)}
