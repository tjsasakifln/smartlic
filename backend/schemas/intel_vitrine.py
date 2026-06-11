"""VITRINE-001 (#1612): Pydantic schemas for public intelligence vitrine.

Páginas públicas /inteligencia/[cnpj] com dados agregados de contratos públicos.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class OrgaoInfo(BaseModel):
    """Órgão comprador com total de contratos e valor."""
    nome: str
    cnpj: str
    total_contratos: int
    valor_total: float


class DistribuicaoItem(BaseModel):
    """Item de distribuição por UF, ano, ou modalidade."""
    chave: str
    quantidade: int
    valor_total: float


class RankingInfo(BaseModel):
    """Posição da empresa no ranking setorial."""
    percentil: float  # e.g., 95.0 = top 5%
    posicao: int
    total_empresas_setor: int
    texto_contexto: str  # "Esta empresa está entre as top 5% do setor Construção"


class IntelVitrineResponse(BaseModel):
    """Resposta completa da vitrine de inteligência pública."""
    cnpj: str
    razao_social: str
    nome_fantasia: Optional[str] = None
    setor_principal: Optional[str] = None
    setor_nome: Optional[str] = None

    total_contratos_12m: int
    valor_total_12m: float
    total_contratos_alltime: int
    valor_total_alltime: float

    ranking: Optional[RankingInfo] = None
    top_orgaos: list[OrgaoInfo] = []
    distribuicao_uf: list[DistribuicaoItem] = []
    distribuicao_ano: list[DistribuicaoItem] = []
    distribuicao_modalidade: list[DistribuicaoItem] = []

    generated_at: datetime
    aviso_legal: str = (
        "Dados públicos do Portal Nacional de Contratações Públicas (PNCP). "
        "Os valores refletem contratos registrados — podem não representar o "
        "total faturado pela empresa no período."
    )
