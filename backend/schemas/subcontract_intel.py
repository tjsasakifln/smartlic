"""SUBINTEL-011 (#1674): Partnership Score schemas.

Response models for GET /v1/subcontract/partnership-score/{cnpj}.
"""

from __future__ import annotations

from pydantic import BaseModel


class SignalDetail(BaseModel):
    """Individual signal detail within the capacity assessment."""

    score: float
    label: str
    description: str
    details: dict


class CapacitySignals(BaseModel):
    """Composite capacity signals derived from subcontract_capacity_signals RPC."""

    repeat_winner: SignalDetail
    large_contract: SignalDetail
    subcontracting_pattern: SignalDetail


class PartnershipScoreResponse(BaseModel):
    """Score de Oportunidade de Parceria for a given CNPJ supplier.

    Overall score (0.0-1.0) indicates how suitable this supplier is as a
    subcontractor or strategic partner based on public contract signals.
    """

    cnpj: str
    razao_social: str
    overall_score: float
    signals: CapacitySignals
    narrative: str | None = None
    disclaimer: str
