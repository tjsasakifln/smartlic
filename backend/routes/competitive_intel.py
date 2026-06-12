"""COMPINT-011 (#1663): Competitive Intelligence route — supplier-level data.
COMPINT-012 (#1666): Competitive Alerts CRUD.

Endpoints:
  GET /v1/intel-concorrente/fornecedor/{cnpj}
    Returns aggregated competitive data for a specific supplier (CNPJ).
    Gated by COMPETITIVE_INTEL_ENABLED + allow_competitive_intel capability.

  POST /v1/intel-concorrente/alerts — create alert
  GET /v1/intel-concorrente/alerts — list user's alerts
  DELETE /v1/intel-concorrente/alerts/{id} — delete alert

Consumes:
  - competitor_territory_map (COMPINT-001 RPC)
  - competitor_win_metrics (COMPINT-002 RPC)
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path

from auth import require_auth
from quota.plan_auth import get_competitive_intel_dependency
from schemas.competitive_intel import (
    AlertaPosicionamento,
    CompetitiveAlertCreate,
    CompetitiveAlertListResponse,
    CompetitiveAlertResponse,
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


# ============================================================================
# COMPINT-012 (#1666): Competitive Alerts CRUD
# ============================================================================


def _validate_alert_cnpj(cnpj: str) -> str:
    """Validate and clean CNPJ."""
    clean = "".join(c for c in cnpj if c.isdigit())
    if len(clean) != 14:
        raise HTTPException(
            status_code=400,
            detail="CNPJ inválido: deve conter 14 dígitos.",
        )
    return clean


@router.post(
    "/intel-concorrente/alerts",
    summary="Create competitive alert (COMPINT-012)",
    response_model=CompetitiveAlertResponse,
    status_code=201,
)
async def create_competitive_alert(
    body: CompetitiveAlertCreate,
    user: dict = Depends(require_auth),
):
    """Create a new competitive alert to monitor a competitor CNPJ."""
    cnpj_clean = _validate_alert_cnpj(body.competitor_cnpj)

    # Validate alert_type
    valid_types = {"new_contract", "new_uf", "new_agency", "new_sector_entrant"}
    if body.alert_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de alerta inválido. Válidos: {', '.join(sorted(valid_types))}",
        )

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        result = await sb_execute(
            sb.table("competitive_alerts")
            .insert({
                "user_id": user["id"],
                "competitor_cnpj": cnpj_clean,
                "alert_type": body.alert_type,
                "enabled": body.enabled,
            })
            .select("*"),
            category="write",
        )
        rows = result.data or []
        if not rows:
            raise HTTPException(status_code=500, detail="Falha ao criar alerta.")
        row = rows[0] if isinstance(rows, list) else rows
        return CompetitiveAlertResponse(
            id=row["id"],
            user_id=row["user_id"],
            competitor_cnpj=row["competitor_cnpj"],
            alert_type=row["alert_type"],
            enabled=row.get("enabled", True),
            created_at=row.get("created_at", now_iso),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create competitive alert: %s", exc)
        raise HTTPException(status_code=500, detail="Falha ao criar alerta.")


@router.get(
    "/intel-concorrente/alerts",
    summary="List user's competitive alerts (COMPINT-012)",
    response_model=CompetitiveAlertListResponse,
)
async def list_competitive_alerts(
    user: dict = Depends(require_auth),
):
    """List all competitive alerts for the authenticated user."""
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("competitive_alerts")
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
        )
        rows = result.data or []
        return CompetitiveAlertListResponse(
            alerts=[
                CompetitiveAlertResponse(
                    id=r["id"],
                    user_id=r["user_id"],
                    competitor_cnpj=r["competitor_cnpj"],
                    alert_type=r["alert_type"],
                    enabled=r.get("enabled", True),
                    created_at=r.get("created_at"),
                )
                for r in rows
            ],
            total=len(rows),
        )
    except Exception as exc:
        logger.error("Failed to list competitive alerts: %s", exc)
        raise HTTPException(status_code=500, detail="Falha ao listar alertas.")


@router.delete(
    "/intel-concorrente/alerts/{alert_id}",
    summary="Delete competitive alert (COMPINT-012)",
    status_code=204,
)
async def delete_competitive_alert(
    alert_id: str,
    user: dict = Depends(require_auth),
):
    """Delete a competitive alert by ID."""
    sb = get_supabase()

    try:
        # Verify ownership
        check = await sb_execute(
            sb.table("competitive_alerts")
            .select("id")
            .eq("id", alert_id)
            .eq("user_id", user["id"])
            .single(),
        )
        if not check.data:
            raise HTTPException(
                status_code=404,
                detail="Alerta não encontrado ou não pertence ao usuário.",
            )

        await sb_execute(
            sb.table("competitive_alerts")
            .delete()
            .eq("id", alert_id)
            .eq("user_id", user["id"]),
            category="write",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to delete competitive alert %s: %s", alert_id, exc)
        raise HTTPException(status_code=500, detail="Falha ao deletar alerta.")
