"""Timeline Intelligence (B2GOPS-014) schemas.

Schemas for the workspace timeline feed — chronological events
for each edital: publicacao, alteracao, impugnacao, esclarecimento,
resultado, homologacao, nota_manual, lembrete.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


VALID_TIMELINE_TIPOS = frozenset({
    "publicacao", "alteracao", "impugnacao", "esclarecimento",
    "resultado", "homologacao", "nota_manual", "lembrete",
})


class TimelineEventoCreate(BaseModel):
    """Request body to create a manual timeline event.

    Only 'nota_manual' and 'lembrete' tipos are allowed via user creation.
    """

    tipo: str = Field(
        ..., description="Tipo do evento: nota_manual ou lembrete"
    )
    titulo: str = Field(
        ..., min_length=1, max_length=500,
        description="Título descritivo do evento",
    )
    descricao: Optional[str] = Field(
        default=None, max_length=5000,
        description="Descrição detalhada do evento (opcional)",
    )


class TimelineEvento(BaseModel):
    """A single timeline event for an edital."""

    id: str
    edital_id: str
    user_id: str
    tipo: str
    titulo: str
    descricao: Optional[str] = None
    critico: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class TimelineResponse(BaseModel):
    """Paginated timeline event list."""

    eventos: list[TimelineEvento]
    total: int
    limit: int
    offset: int
