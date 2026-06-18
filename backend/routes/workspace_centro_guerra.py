"""B2GOPS-012: Centro de Guerra de Pregao — backend routes.

Provides a 360-degree view of a single procurement opportunity:
  - GET  /v1/workspace/centro-guerra/{edital_id}
  - POST /v1/workspace/centro-guerra/{edital_id}/proximos-passos

All endpoints require authentication.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from auth import require_auth
from log_sanitizer import mask_user_id
from schemas.workspace_centro_guerra import (
    CentroGuerraConcorrente,
    CentroGuerraPassosResponse,
    CentroGuerraProximoPassoRequest,
    CentroGuerraResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspace", "centro-guerra"])


# ---------------------------------------------------------------------------
# Proximos passos templates by status
# ---------------------------------------------------------------------------

_PASSOS_POR_STATUS: dict[str, list[str]] = {
    "publicado": [
        "Ler o edital na integra",
        "Verificar documentos de habilitacao exigidos",
        "Avaliar viabilidade financeira",
        "Identificar prazos e datas importantes",
        "Decidir por participacao (go/no-go)",
    ],
    "aberto": [
        "Preparar documentacao de habilitacao",
        "Elaborar proposta tecnica e comercial",
        "Separar comprovantes de qualificacao economica",
        "Revisar minuta do contrato",
        "Agendar entrega presencial se exigida",
    ],
    "em_andamento": [
        "Acompanhar divulgacao de resultados",
        "Preparar recursos para fases recursais",
        "Manter documentacao atualizada",
        "Monitorar possiveis impugnacoes",
    ],
    "suspenso": [
        "Aguardar decisao judicial ou administrativa",
        "Verificar nova data de abertura",
        "Manter documentacao preparada para retomada",
    ],
    "adjudicado": [
        "Verificar resultado da adjudicacao",
        "Preparar documentacao para contratacao",
        "Acompanhar homologacao",
    ],
    "homologado": [
        "Aguardar convocacao para assinatura",
        "Preparar garantia contratual se exigida",
        "Programar inicio da execucao",
    ],
    "cancelado": [
        "Analisar razoes do cancelamento",
        "Identificar nova oportunidade similar",
        "Arquivar documentacao para reference futura",
    ],
}

_DEFAULT_PASSOS = [
    "Analisar edital completo",
    "Verificar requisitos de habilitacao",
    "Avaliar viabilidade da proposta",
    "Preparar documentacao necessaria",
]


def _inferir_status(data_publicacao: Optional[str], data_abertura: Optional[str]) -> str:
    """Infer the bid status based on publication and opening dates."""
    now = datetime.now(timezone.utc)

    try:
        pub = datetime.fromisoformat(data_publicacao.replace("Z", "+00:00")) if data_publicacao else None
    except (ValueError, AttributeError):
        pub = None

    try:
        abertura = datetime.fromisoformat(data_abertura.replace("Z", "+00:00")) if data_abertura else None
    except (ValueError, AttributeError):
        abertura = None

    if pub and pub > now:
        return "publicado"
    if abertura and abertura > now:
        return "aberto"
    if abertura and abertura <= now:
        return "em_andamento"

    return "publicado"


def _gerar_proximos_passos(status: str) -> list[str]:
    """Generate 3-5 next steps based on bid status."""
    return _PASSOS_POR_STATUS.get(status, _DEFAULT_PASSOS)


async def _fetch_edital(sb, edital_id: str, user_id: str) -> Optional[dict]:
    """Fetch basic edital info from pncp_raw_bids."""
    from supabase_client import sb_execute

    result = await sb_execute(
        sb.table("pncp_raw_bids")
        .select(
            "pncp_id, objeto_compra, valor_total_estimado, modalidade_nome, "
            "orgao_razao_social, orgao_cnpj, uf, data_publicacao, data_abertura, "
            "numero_compra"
        )
        .eq("pncp_id", edital_id)
        .limit(1)
    )
    rows = result.data or []
    return rows[0] if rows else None


async def _fetch_pipeline_viability(sb, edital_id: str, user_id: str) -> tuple[Optional[float], Optional[dict]]:
    """Check pipeline_items for viability data."""
    from supabase_client import sb_execute

    result = await sb_execute(
        sb.table("pipeline_items")
        .select("viability_score, viability_factors")
        .eq("pncp_id", edital_id)
        .eq("user_id", user_id)
        .limit(1)
    )
    rows = result.data or []
    if not rows:
        return None, None

    row = rows[0]
    score = row.get("viability_score")
    factors = row.get("viability_factors")
    return (float(score) if score is not None else None), (factors if factors else None)


async def _check_watchlist(sb, edital_id: str, user_id: str) -> bool:
    """Check if the edital is in any of the user's watchlists."""
    from supabase_client import sb_execute

    result = await sb_execute(
        sb.table("workspace_watchlist_matches")
        .select("id")
        .eq("licitacao_id", edital_id)
        .limit(1)
    )
    return bool(result.data)


async def _fetch_concorrentes(sb, orgao_cnpj: Optional[str]) -> list[CentroGuerraConcorrente]:
    """Fetch top 10 suppliers by total contract value for the same orgao."""
    from supabase_client import sb_execute

    if not orgao_cnpj:
        return []

    result = await sb_execute(
        sb.table("pncp_supplier_contracts")
        .select("ni_fornecedor, nome_fornecedor, valor_global")
        .eq("orgao_cnpj", orgao_cnpj)
        .eq("is_active", True)
    )
    rows = result.data or []
    if not rows:
        return []

    # Aggregate by supplier
    agg: dict[str, dict] = {}
    for r in rows:
        cnpj = r.get("ni_fornecedor", "")
        nome = r.get("nome_fornecedor", "N/D")
        valor = float(r.get("valor_global", 0) or 0)
        if cnpj not in agg:
            agg[cnpj] = {"nome": nome, "cnpj": cnpj, "total": 0, "count": 0}
        agg[cnpj]["total"] += valor
        agg[cnpj]["count"] += 1

    sorted_suppliers = sorted(agg.values(), key=lambda x: x["total"], reverse=True)

    return [
        CentroGuerraConcorrente(
            nome=s["nome"],
            cnpj=s["cnpj"],
            valor_total_contratado=round(s["total"], 2),
            numero_contratos=s["count"],
        )
        for s in sorted_suppliers[:10]
    ]


def _safe_str(value: object) -> Optional[str]:
    """Safely convert value to string or None."""
    if value is None:
        return None
    return str(value)


def _safe_float(value: object) -> Optional[float]:
    """Safely convert value to float or None."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/workspace/centro-guerra/{edital_id}", response_model=CentroGuerraResponse)
async def get_centro_guerra(
    edital_id: str,
    user: dict = Depends(require_auth),
) -> CentroGuerraResponse:
    """Full 360-degree view of a procurement opportunity.

    Aggregates data from pncp_raw_bids (basic info), pipeline_items (viability),
    workspace_watchlist_matches (watchlist status), and pncp_supplier_contracts
    (top 10 suppliers for the same orgao).
    """
    user_id = user["id"]
    from supabase_client import get_supabase, CircuitBreakerOpenError

    sb = get_supabase()

    # 1. Fetch basic edital info
    try:
        edital = await _fetch_edital(sb, edital_id, user_id)
    except CircuitBreakerOpenError:
        logger.warning("Circuit breaker open fetching edital %s", mask_user_id(user_id))
        raise HTTPException(status_code=503, detail="Servico temporariamente indisponivel. Tente novamente em instantes.")
    except Exception as e:
        logger.warning("Error fetching edital %s for user %s: %s", edital_id, mask_user_id(user_id), e)
        raise HTTPException(status_code=404, detail="Edital nao encontrado.")

    if not edital:
        raise HTTPException(status_code=404, detail="Edital nao encontrado.")

    # 2. Extract orgao_cnpj for supplier query
    orgao_cnpj = edital.get("orgao_cnpj")

    # 3. Fetch viability data from pipeline (best-effort)
    viabilidade_score: Optional[float] = None
    viabilidade_fatores: Optional[dict] = None
    try:
        viabilidade_score, viabilidade_fatores = await _fetch_pipeline_viability(sb, edital_id, user_id)
    except Exception as e:
        logger.warning(
            "Error fetching viability for edital %s user %s (fail-open): %s",
            edital_id, mask_user_id(user_id), e,
        )

    # 4. Check watchlist status (best-effort)
    na_watchlist = False
    try:
        na_watchlist = await _check_watchlist(sb, edital_id, user_id)
    except Exception as e:
        logger.warning(
            "Error checking watchlist for edital %s user %s (fail-open): %s",
            edital_id, mask_user_id(user_id), e,
        )

    # 5. Fetch top 10 concorrentes (best-effort)
    concorrentes: list[CentroGuerraConcorrente] = []
    try:
        concorrentes = await _fetch_concorrentes(sb, orgao_cnpj)
    except Exception as e:
        logger.warning(
            "Error fetching concorrentes for orgao %s (fail-open): %s",
            orgao_cnpj, e,
        )

    # 6. Infer status and generate proximos passos
    data_publicacao = _safe_str(edital.get("data_publicacao"))
    data_abertura = _safe_str(edital.get("data_abertura"))
    status = _inferir_status(data_publicacao, data_abertura)
    proximos_passos = _gerar_proximos_passos(status)

    return CentroGuerraResponse(
        edital_id=edital_id,
        numero=_safe_str(edital.get("numero_compra")),
        objeto=edital.get("objeto_compra"),
        valor_estimado=_safe_float(edital.get("valor_total_estimado")),
        modalidade=edital.get("modalidade_nome"),
        orgao_nome=edital.get("orgao_razao_social"),
        uf=edital.get("uf"),
        data_publicacao=edital.get("data_publicacao"),
        data_abertura=edital.get("data_abertura"),
        status=status,
        viabilidade_score=viabilidade_score,
        viabilidade_fatores=viabilidade_fatores,
        proximos_passos=proximos_passos,
        concorrentes=concorrentes,
        na_watchlist=na_watchlist,
    )


@router.post("/workspace/centro-guerra/{edital_id}/proximos-passos", response_model=CentroGuerraPassosResponse)
async def update_proximos_passos(
    edital_id: str,
    body: CentroGuerraProximoPassoRequest,
    user: dict = Depends(require_auth),
) -> CentroGuerraPassosResponse:
    """Update/customize the next steps for a bid.

    This is an in-memory operation for the reduced scope — no DB persistence.
    Simply echoes back the provided passos.
    """
    _ = user  # authenticated — we only verify the user is logged in

    if not body.passos:
        raise HTTPException(status_code=422, detail="Ao menos um passo deve ser informado.")

    logger.info(
        "Proximos passos customized for edital %s: %d steps",
        edital_id, len(body.passos),
    )

    return CentroGuerraPassosResponse(
        edital_id=edital_id,
        passos=body.passos,
    )
