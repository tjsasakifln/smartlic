"""PREDINT-021 (#1670): Pydantic schemas for Predictive Intelligence API.

Defines request/response models for the 3 predictive endpoints:
    GET /v1/predint/forecast    — Demand forecast
    GET /v1/predint/seasonality — Seasonal patterns
    GET /v1/predint/renewals    — Renewal alerts
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# Demand Forecast
# ============================================================================


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
# Seasonal Pattern
# ============================================================================


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
# Renewal Alert
# ============================================================================


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
