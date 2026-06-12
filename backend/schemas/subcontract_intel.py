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



# ============================================================================
# SUBINTEL-012 (#1681): Regional Dependency Index
# ============================================================================


class RegionalDependencyItem(BaseModel):
    """Per-UF dependency data for a sector."""

    uf: str = Field(..., description="UF sigla (2 letras)")
    dependency_score: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Percentual de contratos nesta UF (0-100)",
    )
    contract_count: int = Field(..., ge=0, description="Número de contratos na UF")
    total_value: float = Field(
        ..., ge=0.0, description="Valor total dos contratos na UF"
    )


class RegionalDependencyResponse(BaseModel):
    """Response for GET /v1/subcontract/regional-dependency."""

    sector_id: str = Field(..., description="ID do setor consultado")
    uf_distribution: list[RegionalDependencyItem] = Field(
        ..., description="Distribuição de contratos por UF"
    )
    total_contracts: int = Field(..., ge=0, description="Total de contratos no período")
    total_value: float = Field(
        ..., ge=0.0, description="Valor total de contratos no período"
    )
    coverage_ufs: int = Field(
        ..., ge=0, description="Número de UFs com contratos"
    )
    hhi_normalized: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Índice HHI normalizado (1 - HHI). Quanto menor, mais concentrado.",
    )
    risk_level: str = Field(
        ...,
        description="Nível de risco: baixo (>=0.6), medio (0.3-0.6), alto (<0.3)",
    )
    disclaimer: str = Field(
        ..., description="Disclaimer obrigatório sobre a análise"
    )
    generated_at: str = Field(
        ..., description="Timestamp ISO da geração dos dados"
    )
