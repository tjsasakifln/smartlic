"""B2GOPS-012: Centro de Guerra de Pregao — backend schemas.

Provides Pydantic models for the 360-degree bid overview feature.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CentroGuerraConcorrente(BaseModel):
    """A competitor supplier that has contracts with the same orgao."""

    nome: str = "N/D"
    cnpj: str = ""
    valor_total_contratado: float = 0.0
    numero_contratos: int = 0


class CentroGuerraResponse(BaseModel):
    """Consolidated view of a single procurement opportunity."""

    edital_id: str
    numero: Optional[str] = None
    objeto: Optional[str] = None
    valor_estimado: Optional[float] = Field(None, ge=0)
    modalidade: Optional[str] = None
    orgao_nome: Optional[str] = None
    uf: Optional[str] = None
    data_publicacao: Optional[datetime] = None
    data_abertura: Optional[datetime] = None
    status: Optional[str] = None
    viabilidade_score: Optional[float] = Field(None, ge=0, le=100)
    viabilidade_fatores: Optional[dict] = None
    proximos_passos: list[str] = []
    concorrentes: list[CentroGuerraConcorrente] = []
    na_watchlist: bool = False


class CentroGuerraProximoPassoRequest(BaseModel):
    """User customization of next steps for a bid."""

    passos: list[str]


class CentroGuerraPassosResponse(BaseModel):
    """Response after updating/customizing next steps."""

    edital_id: str
    passos: list[str]
