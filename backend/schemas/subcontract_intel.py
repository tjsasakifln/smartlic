"""Pydantic schemas for the Subcontracting Intelligence vertical.

EPIC-SUBINTEL (#1224):
  - SUBINTEL-022 (#1678): Subcontract pSEO block

Every endpoint in the subnet is gated by requires_subcontract_intel()
from quota/plan_auth.py (SUBINTEL-030).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# SUBINTEL-022 (#1678): Subcontract pSEO block
# ============================================================================


class HistoricalSupplier(BaseModel):
    """A historical supplier with similar contracts."""

    cnpj: str = Field(..., description="CNPJ do fornecedor")
    razao_social: Optional[str] = Field(None, description="Razão social")
    similar_contracts_count: int = Field(
        ..., ge=0, description="Número de contratos similares"
    )
    total_value: float = Field(
        ..., ge=0.0, description="Valor total dos contratos"
    )
    avg_value: float = Field(
        ..., ge=0.0, description="Valor médio dos contratos"
    )
    last_contract_year: Optional[int] = Field(
        None, description="Ano do último contrato"
    )
    match_reason: str = Field(
        ..., description="Razão da correspondência"
    )


class SubcontractReason(BaseModel):
    """A reason contributing to the subcontract potential score."""

    reason: str = Field(..., description="Descrição do fator")
    weight: float = Field(
        ..., ge=0.0, le=1.0, description="Peso do fator no score"
    )


class SubcontractBidOpportunityResponse(BaseModel):
    """Response for GET /v1/subcontract/opportunities."""

    bid_id: str = Field(..., description="ID do edital")
    bid_value: float = Field(
        ..., ge=0.0, description="Valor estimado do edital"
    )
    bid_sector: str = Field(
        ..., description="Setor do edital"
    )
    subcontract_potential_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score de potencial de subcontratação (0-1)",
    )
    reasons: list[SubcontractReason] = Field(
        ..., description="Razões para o score"
    )
    historical_suppliers: list[HistoricalSupplier] = Field(
        ..., description="Fornecedores históricos similares"
    )
    disclaimer: str = Field(
        ..., description="Disclaimer obrigatório"
    )
    generated_at: str = Field(
        ..., description="Timestamp ISO da geração dos dados"
    )
