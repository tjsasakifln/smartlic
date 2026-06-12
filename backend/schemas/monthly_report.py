"""REPORT-MONTHLY-001 (#1620): Pydantic models for Monthly Report feature.

Models for the "Panorama Mensal de [Setor]" subscription product (R$97/mes).
"""

from typing import Optional

from pydantic import BaseModel, Field


class MonthlyReportPreviewResponse(BaseModel):
    """Preview data for a sector's monthly report (sample data)."""

    sector_id: str
    sector_name: str
    period: str  # e.g. "2026-05"
    total_licitacoes: int
    total_value: float
    avg_value: float
    top_opportunities: list[dict]
    top_winners: list[dict]
    executive_summary: str
    sample_pdf_available: bool = False


class MonthlyReportSubscribeRequest(BaseModel):
    """Request body for POST /v1/report-mensal/subscribe."""

    sector_id: str = Field(..., min_length=1)
    stripe_price_id: Optional[str] = None


class MonthlyReportSubscriptionResponse(BaseModel):
    """Response model for a monthly report subscription."""

    id: str
    user_id: str
    sector_id: str
    status: str
    stripe_sub_id: Optional[str] = None
    created_at: str


class MonthlyReportSubscriptionsListResponse(BaseModel):
    """Wrapper for list of subscriptions."""

    subscriptions: list[MonthlyReportSubscriptionResponse]
    total: int
    active_count: int
