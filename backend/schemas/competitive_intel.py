"""COMPINT-010/013/014: Pydantic schemas for Competitive Intelligence vertical.

Response models for territory, benchmarks, and dossie endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# COMPINT-010 — Territory / Competitive Landscape
# ---------------------------------------------------------------------------


class CompetitorItem(BaseModel):
    """A single competitor in the leaderboard."""

    cnpj: str = Field(..., description="CNPJ do concorrente")
    razao_social: str = Field(..., description="Nome / razao social")
    total_contratado: float = Field(..., description="Valor total contratado no periodo")
    numero_contratos: int = Field(default=0, description="Numero de contratos no periodo")
    ticket_medio: float = Field(default=0, description="Ticket medio por contrato")
    ufs_atuacao: list[str] = Field(default_factory=list, description="UFs onde atua")
    market_share: float = Field(default=0, description="Market share percentual (0-100)")
    tendencia: str = Field(default="estavel", description="Tendencia: crescimento/estavel/retracao")


class TerritoryUfData(BaseModel):
    """Territory data for a single UF."""

    uf: str = Field(..., description="Sigla da UF")
    total_contratado: float = Field(..., description="Valor total contratado na UF")
    numero_contratos: int = Field(default=0, description="Numero de contratos na UF")
    market_share: float = Field(default=0, description="Market share do concorrente na UF (0-100)")
    orgaos_principais: list[str] = Field(default_factory=list, description="Principais orgaos compradores")
    tendencia: str = Field(default="estavel", description="Tendencia na UF")


class TerritoryData(BaseModel):
    """Territory map data for a single competitor."""

    cnpj: str = Field(..., description="CNPJ do concorrente")
    razao_social: str = Field(..., description="Nome / razao social")
    total_contratado: float = Field(..., description="Valor total contratado")
    total_contratos: int = Field(default=0, description="Total de contratos")
    ufs: list[TerritoryUfData] = Field(default_factory=list, description="Dados por UF")


class CompetitiveLandscapeResponse(BaseModel):
    """Top-level response for GET /v1/intel-concorrente/landscape."""

    setor_id: str = Field(..., description="ID do setor")
    setor_nome: str = Field(..., description="Nome do setor")
    uf: Optional[str] = Field(default=None, description="UF filtrada (opcional)")
    total_contratado: float = Field(..., description="Valor total contratado no setor")
    total_contratos: int = Field(default=0, description="Total de contratos")
    total_concorrentes: int = Field(default=0, description="Total de concorrentes identificados")
    top_concorrentes: list[CompetitorItem] = Field(default_factory=list, description="Top concorrentes")
    periodo: str = Field(default="Ultimos 12 meses", description="Periodo analisado")
    gerado_em: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp de geracao")


# ---------------------------------------------------------------------------
# COMPINT-013 — Sector Benchmarks
# ---------------------------------------------------------------------------


class BenchmarkPercentile(BaseModel):
    """A single percentile value for a metric."""

    p25: float = Field(..., description="Percentil 25")
    p50: float = Field(..., description="Percentil 50 (mediana)")
    p75: float = Field(..., description="Percentil 75")


class CompetitorBenchmark(BaseModel):
    """Benchmark comparison for a single metric."""

    metrica: str = Field(..., description="Nome da metrica (ex: taxa_vitoria, ticket_medio)")
    label: str = Field(..., description="Label amigavel para exibicao")
    valor_concorrente: float = Field(..., description="Valor do concorrente na metrica")
    percentil_concorrente: float = Field(..., description="Percentil do concorrente (0-100)")
    benchmark_setor: BenchmarkPercentile = Field(..., description="Benchmark do setor (P25/P50/P75)")
    descricao: str = Field(default="", description="Tooltip explicativo")


class SectorBenchmarkResponse(BaseModel):
    """Top-level response for GET /v1/intel-concorrente/benchmarks."""

    cnpj: str = Field(..., description="CNPJ do concorrente")
    razao_social: str = Field(..., description="Nome / razao social")
    setor_id: str = Field(..., description="ID do setor")
    setor_nome: str = Field(..., description="Nome do setor")
    metricas: list[CompetitorBenchmark] = Field(default_factory=list, description="Metricas comparativas")
    gerado_em: str = Field(default_factory=lambda: datetime.now().isoformat(), description="Timestamp de geracao")


# ---------------------------------------------------------------------------
# COMPINT-014 — Dossie PDF
# ---------------------------------------------------------------------------


class DossieRequest(BaseModel):
    """Request parameters for dossie generation."""

    setor_id: Optional[str] = Field(default=None, description="Setor para contextualizacao")
    include_llm_summary: bool = Field(default=True, description="Incluir sumario executivo gerado por IA")


class DossieResponse(BaseModel):
    """Response for dossie generation request."""

    cnpj: str = Field(..., description="CNPJ do concorrente")
    job_id: str = Field(..., description="ID do job ARQ para acompanhamento")
    status: str = Field(default="queued", description="Status do job: queued/processing/done/error")
    download_url: Optional[str] = Field(default=None, description="URL para download do PDF quando pronto")
    message: str = Field(default="Dossie sendo gerado em background.", description="Mensagem de status")


class DossieStatusResponse(BaseModel):
    """Status polling response for dossie generation."""

    cnpj: str = Field(..., description="CNPJ do concorrente")
    job_id: str = Field(..., description="ID do job")
    status: str = Field(..., description="Status atual: queued/processing/done/error")
    progress: int = Field(default=0, description="Progresso percentual (0-100)")
    download_url: Optional[str] = Field(default=None, description="URL de download quando concluido")
    error: Optional[str] = Field(default=None, description="Mensagem de erro se aplicavel")

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
