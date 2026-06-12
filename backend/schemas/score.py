"""SCORE-001: Pydantic models for SmartLic Score API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScoreRequest(BaseModel):
    """Single bid score request."""

    bid: dict = Field(..., description="Bid dictionary with modalidade, uf, valor, etc.")
    cnpj: str = Field(..., min_length=14, max_length=14, description="CNPJ to score (14 digits, no mask).")


class ScoreResponse(BaseModel):
    """Single bid score response."""

    probability: float = Field(ge=0.0, le=1.0, description="Estimated win probability (0.0 to 1.0).")
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence proxy (0.0 to 1.0).")
    model_version: str = Field(default="v1", description="Model version identifier.")
    feature_enabled: bool = Field(default=True, description="Whether SmartLic Score is enabled.")


class ScoreBatchRequest(BaseModel):
    """Batch score request — multiple bids, single CNPJ."""

    bids: list[dict] = Field(..., min_length=1, max_length=100, description="List of bid dicts to score.")
    cnpj: str = Field(..., min_length=14, max_length=14, description="CNPJ to score (14 digits, no mask).")


class ScoreBatchResponse(BaseModel):
    """Batch score response."""

    scores: list[ScoreResponse]
    count: int
    model_version: str = Field(default="v1")
    feature_enabled: bool = Field(default=True)
