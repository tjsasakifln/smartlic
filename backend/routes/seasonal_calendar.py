"""PREDINT-003: Seasonal purchase calendar route.

Wraps the predict_seasonal_calendar Supabase RPC function as a FastAPI
endpoint with typed Pydantic response model.

Route:  GET /v1/predict/seasonal-calendar
Auth:   Public (no authentication required — data is public)
RPC:    predict_seasonal_calendar (scalar JSON)
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from schemas.seasonal_calendar import SeasonalCalendarResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/predict", tags=["predictive"])


@router.get(
    "/seasonal-calendar",
    response_model=SeasonalCalendarResponse,
    summary="Calendario sazonal de compras por UF",
    description=(
        "Retorna um calendario sazonal de 12 meses com base no historico "
        "de contratos e licitacoes da UF. Inclui volume medio, quantidade, "
        "setor dominante, orgaos principais, indice de sazonalidade, "
        "tendencia e variacao anual para cada mes."
    ),
)
async def get_seasonal_calendar(
    uf: str = Query(
        ...,
        min_length=2,
        max_length=2,
        description="UF (ex: SP, RJ, SC)",
        pattern=r"^[A-Za-z]{2}$",
    ),
    setores: Optional[list[str]] = Query(
        None,
        description="Optional filter by sector slugs (e.g. engenharia, saude)",
    ),
    anos_historico: int = Query(
        5,
        ge=1,
        le=20,
        description="Number of historical years to analyze (1-20)",
    ),
):
    """Build a seasonal purchase calendar for the given UF.

    Args:
        uf: Two-letter UF code (e.g. "SP", "RJ").
        setores: Optional list of sector names to filter by.
        anos_historico: Number of years of history to analyze (default 5).

    Returns:
        SeasonalCalendarResponse with a 12-month calendar and stats.

    Raises:
        HTTPException 502: If the Supabase RPC call fails.
    """
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    uf_upper = uf.upper()

    rpc_params: dict = {
        "p_uf": uf_upper,
        "p_anos_historico": anos_historico,
    }
    if setores:
        rpc_params["p_setores"] = setores

    try:
        rpc_result = await sb_execute(
            sb.rpc("predict_seasonal_calendar", rpc_params),
            category="rpc",
        )
    except Exception as exc:
        logger.exception(
            "predict_seasonal_calendar RPC failed for uf=%s: %s",
            uf_upper,
            exc,
        )
        raise HTTPException(
            status_code=502,
            detail="Erro ao consultar calendario sazonal. Tente novamente.",
        )

    # supabase-py returns scalar JSON as the data value directly (not a list).
    # Handle both shapes defensively.
    data = getattr(rpc_result, "data", None)
    if isinstance(data, list):
        data = data[0] if data else {}
    payload = data or {}

    # Validate structure
    if "calendario" not in payload or "stats" not in payload:
        logger.error(
            "Unexpected RPC response shape for uf=%s: %s",
            uf_upper,
            list(payload.keys()),
        )
        # Return empty structure instead of crashing
        return SeasonalCalendarResponse(
            calendario=[],
            stats={
                "uf": uf_upper,
                "anos_analisados": anos_historico,
                "total_contratos_base": 0,
                "mes_pico": None,
                "mes_vale": None,
            },
        )

    # Pydantic model construction handles type coercion
    return SeasonalCalendarResponse(**payload)
