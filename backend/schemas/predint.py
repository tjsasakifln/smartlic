"""PREDINT-024 + PREDINT-021: Pydantic models for predictive intelligence.

Combines:
  - PREDINT-024: Predictive alert CRUD schemas  (create/update/list/delete alerts)
  - PREDINT-021: Predictive API schemas           (forecast, seasonality, renewals)
"""

from __future__ import annotations
from datetime import date, datetimefrom typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# PREDINT-024: Predictive Alert CRUD
# ============================================================================


class PredictiveAlertCreate(BaseModel):
    sector_id: str = Field(..., min_length=1, max_length=60)
    alert_type: str = Field(..., pattern=r"^(volume_spike|new_opportunity|recurrence|deadline_approaching)$")
    threshold_value: float = Field(default=0.0, ge=0)
    uf: Optional[str] = Field(None, min_length=2, max_length=2)


class PredictiveAlertUpdate(BaseModel):
    sector_id: Optional[str] = Field(None, min_length=1, max_length=60)
    alert_type: Optional[str] = Field(None, pattern=r"^(volume_spike|new_opportunity|recurrence|deadline_approaching)$")
    threshold_value: Optional[float] = Field(None, ge=0)
    uf: Optional[str] = Field(None, min_length=2, max_length=2)
    enabled: Optional[bool] = None


class PredictiveAlertResponse(BaseModel):
    id: str
    user_id: str
    sector_id: str
    alert_type: str
    threshold_value: float
    uf: Optional[str] = None
    enabled: bool
    last_triggered_at: Optional[str] = None
    created_at: str
    updated_at: str


class PredictiveAlertListResponse(BaseModel):
    alerts: list[PredictiveAlertResponse]
    total: int


def row_to_alert_response(row: dict) -> PredictiveAlertResponse:
    return PredictiveAlertResponse(
        id=row["id"], user_id=row["user_id"], sector_id=row["sector_id"],
        alert_type=row["alert_type"],
        threshold_value=float(row.get("threshold_value", 0)),
        uf=row.get("uf"), enabled=row.get("enabled", True),
        last_triggered_at=row.get("last_triggered_at"),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


# ============================================================================
# PREDINT-021: Demand Forecast# ============================================================================


class DemandForecastItem(BaseModel):
    """A single month in the demand forecast time series."""

    month: str = Field(
        description="Month in YYYY-MM format",
        pattern=r"^\d{4}-\d{2}$",
    )
    bid_count: int = Field(
        ge=0,
        description="Number of bids/contracts in this month",
    )
    total_value: float = Field(
        ge=0,
        description="Total value of contracts in this month",
    )


class DemandForecastRequest(BaseModel):
    """Query parameters for the demand forecast endpoint."""

    sector: Optional[str] = Field(
        default=None,
        description="Sector ID to filter (e.g., 'alimentos'). If omitted, returns all sectors.",
    )
    uf: Optional[str] = Field(
        default=None,
        description="UF filter (2-letter). If omitted, returns national aggregation.",
        pattern=r"^[A-Z]{2}$",
    )
    months: int = Field(
        default=12,
        ge=1,
        le=120,
        description="Number of months to look back (1-120, default 12)",
    )


class DemandForecastResponse(BaseModel):
    """Response from the demand forecast endpoint."""

    sector: Optional[str] = None
    uf: Optional[str] = None
    months: int
    forecast: list[DemandForecastItem]
    total_contracts: int = 0
    total_value: float = 0.0
    feature_enabled: bool = True


# ============================================================================
# PREDINT-021: Seasonal Pattern# ============================================================================


class SeasonalPatternItem(BaseModel):
    """A single month's seasonal average (Jan-Dec)."""

    month_num: int = Field(
        ge=1,
        le=12,
        description="Month number (1=January, 12=December)",
    )
    avg_count: float = Field(
        ge=0,
        description="Average number of contracts in this month over the period",
    )
    avg_value: float = Field(
        ge=0,
        description="Average contract value in this month",
    )


class SeasonalPatternResponse(BaseModel):
    """Response from the seasonal pattern endpoint."""

    sector: Optional[str] = None
    patterns: list[SeasonalPatternItem]
    peak_month: Optional[int] = Field(
        default=None,
        ge=1,
        le=12,
        description="Month with highest average contract count",
    )
    feature_enabled: bool = True


# ============================================================================
# PREDINT-021: Renewal Alert# ============================================================================


class RenewalAlertItem(BaseModel):
    """A single contract approaching renewal."""

    contract_id: int = Field(
        description="Contract ID from pncp_supplier_contracts",
    )
    orgao: str = Field(
        description="Name of the contracting public agency",
    )
    value: float = Field(
        ge=0,
        description="Estimated contract value",
    )
    estimated_expiry: date = Field(
        description="Estimated expiry date (data_assinatura + 1 year heuristic)",
    )


class RenewalAlertRequest(BaseModel):
    """Query parameters for the renewal alerts endpoint."""

    sector: Optional[str] = Field(
        default=None,
        description="Sector ID to filter. If omitted, returns all sectors.",
    )
    days: int = Field(
        default=90,
        ge=1,
        le=365,
        description="Lookahead window in days (1-365, default 90)",
    )


class RenewalAlertResponse(BaseModel):
    """Response from the renewal alerts endpoint."""

    sector: Optional[str] = None
    days: int
    alerts: list[RenewalAlertItem]
    total_count: int = 0
    total_value: float = 0.0
    feature_enabled: bool = True
