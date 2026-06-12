"""MKT-001 (#1616): Subcontract Marketplace Pydantic schemas.

Defines request/response models for the subcontract marketplace MVP:
- SubcontractOpportunity: single opportunity listing
- SubcontractOpportunityResponse: paginated response
- ExpressInterestRequest: express interest form
- ExpressInterestResponse: confirmation
- MarketplaceFilter: query parameters for filtering
- ContactRevealResponse: premium gate contact info
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class SubcontractOpportunity(BaseModel):
    """A single subcontract opportunity listed on the marketplace."""

    id: str
    contract_id: Optional[str] = None
    winner_cnpj: str
    winner_name: Optional[str] = None
    sector: Optional[str] = None
    value: Optional[float] = None
    services_needed: list[str] = Field(default_factory=list)
    status: str = "open"
    uf: Optional[str] = None
    municipio: Optional[str] = None
    orgao_nome: Optional[str] = None
    objeto: Optional[str] = None
    discovery_reason: Optional[str] = None
    created_at: datetime
    interest_count: int = 0


class SubcontractOpportunityResponse(BaseModel):
    """Paginated response for marketplace opportunities."""

    opportunities: list[SubcontractOpportunity]
    total: int
    page: int
    page_size: int
    total_pages: int


class ExpressInterestRequest(BaseModel):
    """Request body for POST /v1/marketplace/express-interest."""

    opportunity_id: str = Field(..., description="UUID da oportunidade")
    message: Optional[str] = Field(
        None,
        max_length=1000,
        description="Mensagem opcional para o vencedor do contrato",
    )


class ExpressInterestResponse(BaseModel):
    """Confirmation of expressed interest."""

    success: bool = True
    message: str = "Interesse registrado com sucesso"


class MarketplaceFilter(BaseModel):
    """Query parameters for filtering marketplace opportunities."""

    setor: Optional[str] = Field(None, description="Filtrar por setor (ex: construcao_civil)")
    uf: Optional[str] = Field(None, description="Filtrar por UF (ex: SP)")
    page: int = Field(default=1, ge=1, description="Pagina (1-based)")
    page_size: int = Field(default=20, ge=1, le=100, description="Itens por pagina")


class ContactRevealResponse(BaseModel):
    """Contact information revealed for Insight+ users."""

    winner_cnpj: str
    winner_name: Optional[str] = None
    winner_email: Optional[str] = None
    winner_phone: Optional[str] = None
    contract_value: Optional[float] = None
    orgao_nome: Optional[str] = None
    message: str = "Dados de contato liberados — plano Insight+"
