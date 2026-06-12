"""SCORE-001 (#1614): Pydantic schemas for SmartLic Score API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    """Request to score a single bid for a given CNPJ."""

    bid_id: str = Field(..., description="Unique identifier for the bid")
    cnpj: str = Field(..., description="Supplier CNPJ (14 digits, no mask)", min_length=14, max_length=14)
    modalidade: str | None = Field(None, description="Procurement modality name")
    uf: str | None = Field(None, description="State UF (2 letters)")
    valor_estimado: float | None = Field(None, ge=0, description="Estimated bid value")
    data_encerramento: str | None = Field(None, description="Proposal deadline (ISO date)")
    porte: str | None = Field(None, description="Company size (MEI, ME, EPP, Medio, Grande)")


class ScoreResponse(BaseModel):
    """Score response for a single bid."""

    bid_id: str
    cnpj: str
    win_probability: float = Field(..., ge=0.0, le=1.0, description="Win probability score (0.0–1.0)")
    score_available: bool = Field(True, description="Whether the ML model was available for scoring")
    model_version: str = Field("v1", description="Model version identifier")


class BatchScoreRequest(BaseModel):
    """Request to score multiple bids for a single CNPJ."""

    cnpj: str = Field(..., description="Supplier CNPJ (14 digits, no mask)", min_length=14, max_length=14)
    bids: list[ScoreRequest] = Field(..., min_length=1, max_length=100, description="List of bids to score")


class BatchScoreResponse(BaseModel):
    """Batch score response."""

    cnpj: str
    scores: list[ScoreResponse]
    mean_probability: float = Field(..., ge=0.0, le=1.0, description="Average win probability across all bids")
    model_version: str = Field("v1")
