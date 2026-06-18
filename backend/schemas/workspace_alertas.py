"""B2GOPS-011 (#2021): Pydantic schemas for workspace watchlist and alertas.

Watchlist — manage editais being monitored.
Alertas — read alerts from user_alerts table via workspace prefix.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------


class WatchlistCreate(BaseModel):
    """Request body for adding an edital to the watchlist."""
    edital_id: str = Field(..., description="PNCP ID or source identifier")
    uf: str = Field(default="", description="Estado (UF) da licitação")
    setor: str = Field(default="", description="Setor para alert matching")
    keywords: List[str] = Field(default_factory=list, description="Keywords extras")


class WatchlistItem(BaseModel):
    """A single watchlist entry."""
    id: str
    user_id: str
    edital_id: str
    uf: str = ""
    setor: str = ""
    keywords: List[str] = Field(default_factory=list)
    created_at: str


class WatchlistResponse(BaseModel):
    """List of watchlist items."""
    items: List[WatchlistItem]
    total: int


# ---------------------------------------------------------------------------
# Alertas (reads from user_alerts table)
# ---------------------------------------------------------------------------


class AlertaItem(BaseModel):
    """A single alerta item (mirrors user_alerts table)."""
    id: str
    user_id: str
    tipo: str = Field(..., alias="type")
    titulo: str = Field(..., alias="title")
    descricao: Optional[str] = Field(default=None, alias="body")
    metadata: Dict[str, Any] = Field(default_factory=dict, alias="data")
    lido: bool = Field(default=False, alias="is_read")
    read_at: Optional[str] = None
    created_at: str

    class Config:
        populate_by_name = True
        allow_population_by_field_name = True


class AlertaResponse(BaseModel):
    """Paginated response for workspace alertas."""
    alertas: List[AlertaItem]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Alert engine schemas
# ---------------------------------------------------------------------------


class WatchlistMatchResult(BaseModel):
    """Result of matching watchlist entries against new editais."""
    edital_id: str
    uf: str = ""
    setor: str = ""
    titulo: str = ""
    orgao: str = ""
    match_type: str = "uf_setor"  # uf_setor, keyword, both
    match_score: float = 0.0
