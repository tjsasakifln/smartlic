"""B2GOPS-013 (#2023): Pydantic schemas for Documentos Colaborativos.

Defines request/response models for workspace documento templates
and user-owned documents CRUD.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, field_validator

# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


class TemplateResponse(BaseModel):
    """Read-only template model returned to the frontend."""

    id: str
    nome: str
    tipo: str
    descricao: Optional[str] = None
    conteudo: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------

VALID_DOCUMENTO_TIPOS = {
    "proposta",
    "declaracao",
    "recurso",
    "impugnacao",
    "carta",
    "planilha",
}


class DocumentoCreate(BaseModel):
    """Request body for POST /v1/workspace/documentos."""

    titulo: str
    tipo: str
    edital_id: Optional[str] = None
    template_id: Optional[str] = None

    @field_validator("tipo")
    @classmethod
    def _validate_tipo(cls, v: str) -> str:
        if v not in VALID_DOCUMENTO_TIPOS:
            raise ValueError(
                f"tipo must be one of: {', '.join(sorted(VALID_DOCUMENTO_TIPOS))}"
            )
        return v


class DocumentoUpdate(BaseModel):
    """Request body for PATCH /v1/workspace/documentos/{id}."""

    titulo: Optional[str] = None
    conteudo: Optional[str] = None


class DocumentoResponse(BaseModel):
    """Full document model returned to the frontend."""

    id: str
    user_id: str
    edital_id: Optional[str] = None
    template_id: Optional[str] = None
    titulo: str
    conteudo: str
    tipo: str
    variaveis: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime


class DocumentoListResponse(BaseModel):
    """Paginated list of user documents."""

    documentos: list[DocumentoResponse]
    total: int


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


class RenderDocumentoRequest(BaseModel):
    """Request body for POST /v1/workspace/documentos/{id}/render.

    Fetch edital data from pncp_raw_bids by edital_id and substitute
    {{variavel}} patterns in the document conteudo.
    """

    edital_id: str
