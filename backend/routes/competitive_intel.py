"""COMPINT-011 (#1663): Competitive Intelligence route — supplier-level data.

GET /v1/intel-concorrente/fornecedor/{cnpj}
  Returns aggregated competitive data for a specific supplier (CNPJ).
  Gated by COMPETITIVE_INTEL_ENABLED + allow_competitive_intel capability.

Consumes:
  - competitor_territory_map (COMPINT-001 RPC)
  - competitor_win_metrics (COMPINT-002 RPC)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path

from quota.plan_auth import get_competitive_intel_dependency
from schemas.competitive_intel import (
    AlertaPosicionamento,
    ConcorrenteInfo,
    FornecedorIntelResponse,
    TerritorioStats,
    WinMetrics,
)
from supabase_client import get_supabase, sb_execute

logger = logging.getLogger(__name__)

router = APIRouter(tags=["competitive_intel"])

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
_competitive_intel_dep = get_competitive_intel_dependency()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_alertas(
    territorio: list[dict],
    stats: dict,
) -> list[dict]:
    """Derive positioning alerts from territory data."""
    alertas: list[dict] = []

    # Tendência de expansão — novas UFs com crescimento
    expanding_ufs = [
        t for t in territorio
        if t.get("tendencia") in ("crescendo", "expansao", "nova")
    ]
    if expanding_ufs:
        nomes = [t["uf"] for t in expanding_ufs[:3]]
        alertas.append({
            "tipo": "expansao",
            "mensagem": f"Expandindo atuação para {'/'.join(nomes)}",
            "severidade": "info",
        })

    # Crescimento anual
    crescimento = stats.get("crescimento_anual")
    if crescimento is not None:
        if crescimento > 30:
            alertas.append({
                "tipo": "crescimento",
                "mensagem": f"Crescimento de {crescimento:.0f}% em contratos no último ano",
                "severidade": "success",
            })
        elif crescimento > 10:
            alertas.append({
                "tipo": "crescimento",
                "mensagem": f"Crescimento de {crescimento:.0f}% em contratos",
                "severidade": "info",
            })
        elif crescimento < -10:
            alertas.append({
                "tipo": "crescimento",
                "mensagem": f"Retração de {abs(crescimento):.0f}% em contratos no último ano",
                "severidade": "warning",
            })

    # Player dominante em UF com market share alto
    dominant_ufs = [
        t for t in territorio
        if t.get("market_share_uf") is not None and t["market_share_uf"] > 0.3
    ]
    if dominant_ufs:
        top = max(dominant_ufs, key=lambda t: t["market_share_uf"])
        share_pct = top["market_share_uf"] * 100
        alertas.append({
            "tipo": "dominio",
            "mensagem": f"Player dominante em {top['uf']} com {share_pct:.0f}% de market share",
            "severidade": "success",
        })

    return alertas


def _extract_territorio(raw: list) -> list[dict]:
    """Normalize territory entries from RPC output."""
    return [
        {
            "uf": t.get("uf", ""),
            "contratos": t.get("contratos", 0) or 0,
            "valor_total": float(t.get("valor_total", 0) or 0),
            "ticket_medio_uf": float(t.get("ticket_medio_uf", 0) or 0),
            "orgaos_principais": t.get("orgaos_principais", []),
            "market_share_uf": (
                float(t["market_share_uf"])
                if t.get("market_share_uf") is not None
                else None
            ),
            "tendencia": t.get("tendencia"),
        }
        for t in (raw or [])
    ]


def _extract_orgaos(raw: list) -> list[dict]:
    """Normalize orgaos_favoritos from RPC output."""
    return [
        {
            "orgao_nome": o.get("orgao_nome", ""),
            "contratos": o.get("contratos", 0) or 0,
            "valor_total": float(o.get("valor_total", 0) or 0),
            "categorias": o.get("categorias", []),
            "ultima_vitoria": o.get("ultima_vitoria"),
            "frequencia_anual": (
                float(o["frequencia_anual"])
                if o.get("frequencia_anual") is not None
                else None
            ),
        }
        for o in (raw or [])
    ]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/intel-concorrente/fornecedor/{cnpj}",
    summary="Competitive Intelligence data for a supplier CNPJ (COMPINT-011)",
    response_model=FornecedorIntelResponse,
)
async def fornecedor_competitive_intel(
    cnpj: str = Path(..., description="Supplier CNPJ (14 digits)"),
    anos: int = 3,
    user: dict = Depends(_competitive_intel_dep),
):
    """Return competitive intelligence data for *cnpj*.

    Aggregates:
    - Territorial map (COMPINT-001 RPC)
    - Win metrics (COMPINT-002 RPC)
    - Derived positioning alerts
    """
    # Validate CNPJ format
    cnpj_clean = "".join(c for c in cnpj if c.isdigit())
    if len(cnpj_clean) != 14:
        raise HTTPException(
            status_code=400,
            detail="CNPJ inválido: deve conter 14 dígitos.",
        )

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()

    # --- Fetch territory map ---
    try:
        territory_resp = await sb_execute(
            sb.rpc("competitor_territory_map", {
                "p_cnpj": cnpj_clean,
                "p_anos": anos,
            })
        )
        territory_data = territory_resp.data
    except Exception as exc:
        logger.error("competitor_territory_map RPC failed for %s: %s", cnpj_clean, exc)
        raise HTTPException(
            status_code=502,
            detail="Falha ao buscar dados territoriais do concorrente.",
        )

    if not territory_data or isinstance(territory_data, dict) and "erro" in territory_data:
        # No data for this supplier or error from RPC
        raise HTTPException(
            status_code=404,
            detail="Dados de inteligência concorrencial não disponíveis para este CNPJ.",
        )

    # --- Fetch win metrics ---
    win_metrics_raw: Optional[dict] = None
    try:
        win_resp = await sb_execute(
            sb.rpc("competitor_win_metrics", {
                "p_cnpj": cnpj_clean,
                "p_anos": anos,
            })
        )
        win_data = win_resp.data
        if isinstance(win_data, dict) and "win_metrics" in win_data:
            win_metrics_raw = win_data["win_metrics"]
    except Exception as exc:
        logger.warning("competitor_win_metrics RPC failed for %s: %s", cnpj_clean, exc)
        # Non-blocking — win metrics are additive

    # --- Build response ---
    concorrente_raw = territory_data.get("concorrente", {})
    territorio_raw = territory_data.get("territorio", [])
    orgaos_raw = territory_data.get("orgaos_favoritos", [])
    stats_raw = territory_data.get("stats", {})

    territorio = _extract_territorio(territorio_raw)
    orgaos_favoritos = _extract_orgaos(orgaos_raw)

    # Derive positioning alerts
    alertas_raw = _derive_alertas(territorio_raw, stats_raw)

    # Build win_metrics if available
    win_metrics: Optional[WinMetrics] = None
    if win_metrics_raw:
        win_metrics = WinMetrics(
            taxa_vitoria_estimada=win_metrics_raw.get("taxa_vitoria_estimada"),
            velocidade_crescimento=win_metrics_raw.get("velocidade_crescimento"),
            tendencia=win_metrics_raw.get("tendencia"),
            ticket_p25=(
                float(win_metrics_raw["ticket_p25"])
                if win_metrics_raw.get("ticket_p25") is not None
                else None
            ),
            ticket_p50=(
                float(win_metrics_raw["ticket_p50"])
                if win_metrics_raw.get("ticket_p50") is not None
                else None
            ),
            ticket_p75=(
                float(win_metrics_raw["ticket_p75"])
                if win_metrics_raw.get("ticket_p75") is not None
                else None
            ),
            ticket_p90=(
                float(win_metrics_raw["ticket_p90"])
                if win_metrics_raw.get("ticket_p90") is not None
                else None
            ),
            indice_concentracao=win_metrics_raw.get("indice_concentracao"),
            dependencia_publica=win_metrics_raw.get("dependencia_publica"),
        )

    return FornecedorIntelResponse(
        concorrente=ConcorrenteInfo(
            cnpj=concorrente_raw.get("cnpj", cnpj_clean),
            nome=concorrente_raw.get("nome", ""),
            total_contratos=concorrente_raw.get("total_contratos", 0) or 0,
            ticket_medio=float(concorrente_raw.get("ticket_medio", 0) or 0),
            ticket_mediana=float(concorrente_raw.get("ticket_mediana", 0) or 0),
            valor_total_contratado=float(
                concorrente_raw.get("valor_total_contratado", 0) or 0
            ),
        ),
        territorio=territorio,
        orgaos_favoritos=orgaos_favoritos,
        stats=TerritorioStats(
            ufs_atuacao=stats_raw.get("ufs_atuacao", 0) or 0,
            orgaos_unicos=stats_raw.get("orgaos_unicos", 0) or 0,
            anos_atuacao=stats_raw.get("anos_atuacao", 0) or 0,
            crescimento_anual=(
                float(stats_raw["crescimento_anual"])
                if stats_raw.get("crescimento_anual") is not None
                else None
            ),
            tendencia_posicionamento=stats_raw.get("tendencia_posicionamento"),
        ),
        win_metrics=win_metrics,
        alertas=[
            AlertaPosicionamento(**a) for a in alertas_raw
        ],
        feature_enabled=True,
        generated_at=now_iso,
    )
