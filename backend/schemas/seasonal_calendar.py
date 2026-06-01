"""PREDINT-003: Pydantic models for predict_seasonal_calendar RPC.

These models match the JSON shape returned by the Supabase RPC function
predict_seasonal_calendar and define the response_model for the route.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class MesCalendario(BaseModel):
    """Single month entry in the seasonal calendar."""

    mes: int = Field(..., ge=1, le=12, description="Month number (1-12)")
    volume_medio: float = Field(
        ..., description="Average total contract value for this month"
    )
    quantidade_media: float = Field(
        ..., description="Average number of contracts/opportunities for this month"
    )
    setor_dominante: str = Field(
        ..., description="Most frequent sector in this month"
    )
    orgaos_principais: list[str] = Field(
        ..., description="Top 5 public buyers in this month"
    )
    indice_sazonalidade: float = Field(
        ...,
        description="Seasonality index: 0 = at average, >0 = detectable seasonality",
    )
    tendencia: str = Field(
        ...,
        description="Trend direction: crescimento | estabilidade | declinio",
    )
    variacao_anual: float = Field(
        ...,
        description="Year-over-year relative change in average volume",
    )


class SeasonalCalendarStats(BaseModel):
    """Aggregate statistics for the seasonal calendar."""

    uf: str = Field(..., description="UF code (uppercase)")
    anos_analisados: int = Field(..., description="Number of years analyzed")
    total_contratos_base: int = Field(
        ..., description="Total number of contracts/bids in the analysis base"
    )
    mes_pico: Optional[int] = Field(
        None, ge=1, le=12, description="Month with highest average volume"
    )
    mes_vale: Optional[int] = Field(
        None, ge=1, le=12, description="Month with lowest average volume"
    )


class SeasonalCalendarResponse(BaseModel):
    """Full response from predict_seasonal_calendar RPC."""

    calendario: list[MesCalendario] = Field(
        ..., description="Array of 12 monthly entries (one per month)"
    )
    stats: SeasonalCalendarStats = Field(
        ..., description="Aggregate statistics"
    )
