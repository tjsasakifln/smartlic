"""Pydantic schemas for workspace integration channels — B2GOPS-015 (#2025).

Reduced scope: CRUD for integration channels + test endpoint only.
No dispatcher, no retry, no complex templates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

TipoCanal = Literal["slack", "teams", "email"]

__all__ = [
    "CanalIntegracaoCreate",
    "CanalIntegracao",
    "TestNotificacaoResponse",
    "TipoCanal",
]


class CanalIntegracaoCreate(BaseModel):
    """Request body for POST /v1/workspace/integracoes/canais."""

    tipo: TipoCanal
    nome: str = Field(..., min_length=1, max_length=100)
    url: Optional[str] = Field(None, description="Webhook URL (required for slack/teams)")
    email_destino: Optional[str] = Field(None, description="Email address (required for email)")
    eventos: list[str] = Field(default_factory=list)


class CanalIntegracao(BaseModel):
    """Public integration channel representation returned by the API."""

    id: str
    user_id: str
    tipo: TipoCanal
    nome: str
    url: Optional[str] = None
    email_destino: Optional[str] = None
    eventos: list[str] = Field(default_factory=list)
    ativo: bool = True
    created_at: datetime
    updated_at: datetime


class TestNotificacaoResponse(BaseModel):
    """Response from the test notification endpoint."""

    sucesso: bool
    mensagem: str
