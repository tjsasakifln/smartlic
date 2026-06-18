"""Pydantic models for workspace B2GOPS-010 (#2020).

Defines schemas for the workspace collaborative hub endpoints.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EditaisHojeItem(BaseModel):
    """A single procurement opportunity published today."""

    pncp_id: str | None = Field(None, description="PNCP identifier")
    orgao: str | None = Field(None, description="Issuing government agency name")
    uf: str | None = Field(None, description="State abbreviation (UF)")
    objeto: str | None = Field(None, description="Procurement object description")
    valor_estimado: float | None = Field(None, description="Estimated value")
    data_publicacao: str | None = Field(None, description="Publication date (ISO 8601)")
    data_encerramento: str | None = Field(None, description="Closing date (ISO 8601)")
    link_pncp: str | None = Field(None, description="Full URL to PNCP page")
    modalidade: str | None = Field(None, description="Procurement modality code")
    numero_compra: str | None = Field(None, description="Procurement number / edital number")


class EditaisHojeResponse(BaseModel):
    """Response wrapper for today's procurement opportunities."""

    items: list[EditaisHojeItem] = Field(default_factory=list, description="List of today's opportunities")
    total: int = Field(0, description="Total count of items returned")


class WorkspaceResumo(BaseModel):
    """Aggregated summary for the workspace dashboard."""

    editais_hoje_count: int = Field(0, description="Number of procurement opportunities published today")
    pipeline_count: int = Field(0, description="Number of items in the user's pipeline")
    pipeline_prazo_proximo: int = Field(0, description="Number of pipeline items with deadlines within 7 days")
    alerts_unread_count: int = Field(0, description="Number of unread user alerts")
