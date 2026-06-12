"""COMPINT-011 (#1663): Competitive Intelligence schemas.

FornecedorIntelResponse — returned by GET /v1/intel-concorrente/fornecedor/{cnpj}.
Aggregates data from competitor_territory_map (COMPINT-001) and
competitor_win_metrics (COMPINT-002) RPCs.

COMPINT-012 (#1666): Competitive Alert schemas.
CompetitiveAlertCreate — POST body for creating an alert.
CompetitiveAlertResponse — response for alert CRUD.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ============================================================================
# COMPINT-011: Fornecedor Intel Response
# ============================================================================


class TerritorioEntry(BaseModel):
    """Per-UF competitive territory data."""

    uf: str
    contratos: int
    valor_total: float
    ticket_medio_uf: float
    orgaos_principais: list[str] = []
    market_share_uf: Optional[float] = None
    tendencia: Optional[str] = None


class OrgaoFavorito(BaseModel):
    """Favorite (most-contracted) agencies."""

    orgao_nome: str
    contratos: int
    valor_total: float
    categorias: list[str] = []
    ultima_vitoria: Optional[str] = None
    frequencia_anual: Optional[float] = None


class TerritorioStats(BaseModel):
    """Aggregate territorial statistics."""

    ufs_atuacao: int
    orgaos_unicos: int
    anos_atuacao: int
    crescimento_anual: Optional[float] = None
    tendencia_posicionamento: Optional[str] = None


class ConcorrenteInfo(BaseModel):
    """High-level competitor information."""

    cnpj: str
    nome: str
    total_contratos: int
    ticket_medio: float
    ticket_mediana: float
    valor_total_contratado: float


class WinMetrics(BaseModel):
    """Win-rate and performance metrics."""

    taxa_vitoria_estimada: Optional[float] = None
    velocidade_crescimento: Optional[float] = None
    tendencia: Optional[str] = None
    ticket_p25: Optional[float] = None
    ticket_p50: Optional[float] = None
    ticket_p75: Optional[float] = None
    ticket_p90: Optional[float] = None
    indice_concentracao: Optional[float] = None
    dependencia_publica: Optional[float] = None


class AlertaPosicionamento(BaseModel):
    """Derived positioning alert."""
    tipo: str  # "expansao", "crescimento", "dominio", "novo_entrante"
    mensagem: str
    severidade: str = "info"  # "info", "warning", "success"


class FornecedorIntelResponse(BaseModel):
    """Complete competitive intelligence response for a supplier CNPJ.

    Returned by GET /v1/intel-concorrente/fornecedor/{cnpj}.
    """

    concorrente: ConcorrenteInfo
    territorio: list[TerritorioEntry]
    orgaos_favoritos: list[OrgaoFavorito]
    stats: TerritorioStats
    win_metrics: Optional[WinMetrics] = None
    alertas: list[AlertaPosicionamento] = []
    feature_enabled: bool = True
    generated_at: str = ""


# ============================================================================
# COMPINT-012: Competitive Alert schemas
# ============================================================================


class CompetitiveAlertCreate(BaseModel):
    """POST body for creating a competitive alert."""

    competitor_cnpj: str = Field(
        ..., description="CNPJ do concorrente a monitorar (14 dígitos)"
    )
    alert_type: str = Field(
        "new_contract",
        description="Tipo de alerta: new_contract, new_uf, new_agency, new_sector_entrant",
    )
    enabled: bool = True


class CompetitiveAlertResponse(BaseModel):
    """Response model for a competitive alert."""

    id: str
    user_id: str
    competitor_cnpj: str
    alert_type: str
    enabled: bool
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class CompetitiveAlertListResponse(BaseModel):
    """List of competitive alerts for the current user."""

    alerts: list[CompetitiveAlertResponse]
    total: int
