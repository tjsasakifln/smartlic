"""WIDGET-COMPINT-001: Pydantic schemas for Competitive Intelligence Widget.

Response models for 4 themes: market-share, top-winners, monthly-trend, orgao-ranking.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Individual data items
# ---------------------------------------------------------------------------


class FornecedorShare(BaseModel):
    """A single supplier's market share data."""

    nome: str = Field(..., description="Nome do fornecedor")
    cnpj: str = Field(..., description="CNPJ do fornecedor")
    percentual: float = Field(..., description="Percentual de participação no valor total")
    valor: float = Field(..., description="Valor total em contratos")
    contratos: int = Field(default=0, description="Número de contratos")


class WinnerItem(BaseModel):
    """A single winner entry with growth indicator."""

    nome: str = Field(..., description="Nome do fornecedor")
    cnpj: str = Field(..., description="CNPJ do fornecedor")
    contratos: int = Field(..., description="Número de contratos no período")
    valor_total: float = Field(..., description="Valor total em contratos")
    crescimento: Optional[str] = Field(default=None, description="Indicador de crescimento (ex: +15%)")


class MesSerie(BaseModel):
    """A single month in the time series."""

    mes: str = Field(..., description="Mês no formato YYYY-MM")
    valor: float = Field(..., description="Valor total de contratos no mês")
    contratos: int = Field(..., description="Número de contratos no mês")


class OrgaoItem(BaseModel):
    """A single public buyer organization."""

    nome: str = Field(..., description="Nome do órgão comprador")
    cnpj: str = Field(..., description="CNPJ do órgão")
    valor: float = Field(..., description="Valor total em contratos")
    contratos: int = Field(..., description="Número de contratos")


# ---------------------------------------------------------------------------
# Theme-specific response bodies
# ---------------------------------------------------------------------------


class MarketShareData(BaseModel):
    """Data payload for market-share theme."""

    valor_total: float = Field(..., description="Valor total de contratos no período")
    total_contratos: int = Field(..., description="Número total de contratos")
    top_fornecedores: list[FornecedorShare] = Field(
        default_factory=list, description="Top fornecedores com participação"
    )
    concentracao: str = Field(
        default="Média", description="Nível de concentração: Baixa/Média/Alta"
    )


class TopWinnersData(BaseModel):
    """Data payload for top-winners theme."""

    winners: list[WinnerItem] = Field(
        default_factory=list, description="Top vencedores com crescimento"
    )


class MonthlyTrendData(BaseModel):
    """Data payload for monthly-trend theme."""

    serie: list[MesSerie] = Field(
        default_factory=list, description="Série temporal mensal"
    )
    tendencia: str = Field(
        default="estavel", description="Tendência: crescimento/estavel/queda"
    )


class OrgaoRankingData(BaseModel):
    """Data payload for orgao-ranking theme."""

    orgaos: list[OrgaoItem] = Field(
        default_factory=list, description="Ranking de órgãos compradores"
    )


# ---------------------------------------------------------------------------
# Unified response wrapper (theme determines which data field is populated)
# ---------------------------------------------------------------------------

THEME_TYPES = {"market-share", "top-winners", "monthly-trend", "orgao-ranking"}


class WidgetIntelResponse(BaseModel):
    """Top-level response for GET /v1/widget/competitive-intel."""

    tema: str = Field(..., description="Tema do widget (market-share | top-winners | monthly-trend | orgao-ranking)")
    setor: str = Field(..., description="Nome do setor")
    uf: Optional[str] = Field(default=None, description="UF filtrada (opcional)")
    periodo: str = Field(default="Últimos 12 meses", description="Período analisado")
    dados: MarketShareData | TopWinnersData | MonthlyTrendData | OrgaoRankingData = Field(
        ..., description="Dados do tema específico"
    )
