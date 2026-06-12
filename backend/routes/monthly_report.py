"""REPORT-MONTHLY-001 (#1620): Monthly Report routes.

Endpoints for the "Panorama Mensal de [Setor]" subscription product (R$97/mes):
- GET /v1/report-mensal/preview/{setor} — Preview sample data for a sector
- POST /v1/report-mensal/subscribe — Subscribe to monthly report
- GET /v1/report-mensal/subscriptions — List subscriptions
- POST /v1/report-mensal/cancel/{id} — Cancel a subscription

Feature flag: MONTHLY_REPORT_ENABLED (config/features.py)
"""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import require_auth
from config.features import get_feature_flag
from schemas.monthly_report import (
    MonthlyReportPreviewResponse,
    MonthlyReportSubscribeRequest,
    MonthlyReportSubscriptionResponse,
    MonthlyReportSubscriptionsListResponse,
)
from sectors import SECTORS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monthly_report"])


# ---------------------------------------------------------------------------
# GET /v1/report-mensal/preview/{setor} — Preview sample data
# ---------------------------------------------------------------------------


@router.get(
    "/report-mensal/preview/{setor}",
    summary="Preview monthly report data for a sector (REPORT-MONTHLY-001)",
    response_model=MonthlyReportPreviewResponse,
)
async def preview_monthly_report(
    request: Request,
    setor: str,
):
    if not get_feature_flag("MONTHLY_REPORT_ENABLED", True):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")

    sector_id_clean = setor.strip().lower()
    if sector_id_clean not in SECTORS:
        raise HTTPException(
            status_code=404,
            detail=f"Setor '{setor}' não encontrado. Setores válidos: {', '.join(sorted(SECTORS.keys()))}",
        )

    sector = SECTORS[sector_id_clean]
    now = datetime.now(timezone.utc)
    last_month = (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    # Generate preview data from the datalake
    try:
        data = await _generate_preview(sector_id_clean, sector.name, last_month)
        return MonthlyReportPreviewResponse(**data)
    except Exception as e:
        logger.error("Monthly report preview failed for %s: %s", sector_id_clean, e)
        # Return synthetic preview on error
        return MonthlyReportPreviewResponse(
            sector_id=sector_id_clean,
            sector_name=sector.name,
            period=last_month,
            total_licitacoes=0,
            total_value=0,
            avg_value=0,
            top_opportunities=[],
            top_winners=[],
            executive_summary=f"Relatório mensal do setor de {sector.name}. "
                              f"Dados completos disponíveis para assinantes.",
            sample_pdf_available=False,
        )


# ---------------------------------------------------------------------------
# POST /v1/report-mensal/subscribe — Subscribe to monthly report
# ---------------------------------------------------------------------------


@router.post(
    "/report-mensal/subscribe",
    summary="Subscribe to monthly report (REPORT-MONTHLY-001)",
    response_model=MonthlyReportSubscriptionResponse,
)
async def subscribe_monthly_report(
    request: Request,
    body: MonthlyReportSubscribeRequest,
    user_id: str = Depends(require_auth),
):
    if not get_feature_flag("MONTHLY_REPORT_ENABLED", True):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")

    if body.sector_id not in SECTORS:
        raise HTTPException(
            status_code=400,
            detail=f"Setor '{body.sector_id}' não é válido.",
        )

    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()

    # Check if already subscribed
    existing = await sb_execute(
        sb.table("monthly_report_subscriptions")
        .select("id, status")
        .eq("user_id", user_id)
        .eq("sector_id", body.sector_id)
        .single()
    )

    if existing.data:
        if existing.data.get("status") == "active":
            raise HTTPException(
                status_code=400,
                detail="Você já está inscrito neste relatório mensal.",
            )
        # Re-activate canceled subscription
        updated = await sb_execute(
            sb.table("monthly_report_subscriptions")
            .update({"status": "active"})
            .eq("id", existing.data["id"])
            .execute()
        )
        row = (updated.data or [None])[0] or existing.data
    else:
        # Create new subscription
        created = await sb_execute(
            sb.table("monthly_report_subscriptions")
            .insert({
                "user_id": user_id,
                "sector_id": body.sector_id,
                "stripe_sub_id": body.stripe_price_id,
            })
            .execute()
        )
        if not created.data or len(created.data) == 0:
            raise HTTPException(status_code=500, detail="Falha ao criar assinatura.")
        row = created.data[0]

    logger.info("User %s subscribed to monthly report for sector '%s'", user_id[:8], body.sector_id)

    return MonthlyReportSubscriptionResponse(
        id=row["id"],
        user_id=row["user_id"],
        sector_id=row["sector_id"],
        status=row["status"],
        stripe_sub_id=row.get("stripe_sub_id"),
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# GET /v1/report-mensal/subscriptions — List user's subscriptions
# ---------------------------------------------------------------------------


@router.get(
    "/report-mensal/subscriptions",
    summary="List monthly report subscriptions (REPORT-MONTHLY-001)",
    response_model=MonthlyReportSubscriptionsListResponse,
)
async def list_subscriptions(
    request: Request,
    user_id: str = Depends(require_auth),
):
    if not get_feature_flag("MONTHLY_REPORT_ENABLED", True):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")

    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    resp = await sb_execute(
        sb.table("monthly_report_subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
    )

    rows = resp.data or []
    active_count = sum(1 for r in rows if r.get("status") == "active")

    subscriptions = [
        MonthlyReportSubscriptionResponse(
            id=r["id"],
            user_id=r["user_id"],
            sector_id=r["sector_id"],
            status=r["status"],
            stripe_sub_id=r.get("stripe_sub_id"),
            created_at=r["created_at"],
        )
        for r in rows
    ]

    return MonthlyReportSubscriptionsListResponse(
        subscriptions=subscriptions,
        total=len(subscriptions),
        active_count=active_count,
    )


# ---------------------------------------------------------------------------
# POST /v1/report-mensal/cancel/{id} — Cancel a subscription
# ---------------------------------------------------------------------------


@router.post(
    "/report-mensal/cancel/{id}",
    summary="Cancel monthly report subscription (REPORT-MONTHLY-001)",
)
async def cancel_subscription(
    request: Request,
    id: str,
    user_id: str = Depends(require_auth),
):
    if not get_feature_flag("MONTHLY_REPORT_ENABLED", True):
        raise HTTPException(status_code=404, detail="Recurso não disponível.")

    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()

    # Find subscription
    resp = await sb_execute(
        sb.table("monthly_report_subscriptions")
        .select("id, status")
        .eq("id", id)
        .eq("user_id", user_id)
        .single()
    )

    if not resp.data:
        raise HTTPException(status_code=404, detail="Assinatura não encontrada.")

    if resp.data.get("status") == "canceled":
        raise HTTPException(status_code=400, detail="Assinatura já está cancelada.")

    await sb_execute(
        sb.table("monthly_report_subscriptions")
        .update({"status": "canceled"})
        .eq("id", id)
        .execute()
    )

    logger.info("User %s canceled monthly report subscription %s", user_id[:8], id[:8])

    return {"message": "Assinatura cancelada com sucesso.", "subscription_id": id}


# ---------------------------------------------------------------------------
# Preview data generation
# ---------------------------------------------------------------------------


async def _generate_preview(sector_id: str, sector_name: str, period: str) -> dict:
    """Generate preview data from pncp_supplier_contracts."""
    from supabase_client import get_supabase, sb_execute
    from resilience.budget import _run_with_budget

    sb = get_supabase()
    now = datetime.now(timezone.utc)
    data_inicial = (now - timedelta(days=60)).strftime("%Y-%m-%d")

    keywords_lower = {kw.lower() for kw in SECTORS[sector_id].keywords} if sector_id in SECTORS else set()

    async def _fetch_data() -> list[dict]:
        batch_size = 500
        all_rows: list[dict] = []
        offset = 0
        while len(all_rows) < 2000:
            end = offset + batch_size - 1
            query = (
                sb.table("pncp_supplier_contracts")
                .select("ni_fornecedor,nome_fornecedor,valor_global,data_assinatura,objeto_contrato,orgao_nome")
                .eq("is_active", True)
                .gte("data_assinatura", data_inicial)
                .order("valor_global", desc=True)
                .range(offset, end)
            )
            resp = await sb_execute(query)
            batch = resp.data or []
            if not batch:
                break
            all_rows.extend(batch)
            if len(batch) < batch_size:
                break
            offset += batch_size
        return all_rows

    rows = await _run_with_budget(
        _fetch_data(),
        budget=6.0,
        phase="route",
        source="monthly_report._generate_preview",
    )

    # Filter by keywords
    if keywords_lower:
        rows = [
            row for row in rows
            if any(kw in (row.get("objeto_contrato") or "").lower() for kw in keywords_lower)
        ]

    total_value = sum(float(row.get("valor_global") or 0) for row in rows)
    total_licitacoes = len(rows)
    avg_value = total_value / total_licitacoes if total_licitacoes > 0 else 0

    # Top opportunities (highest value)
    top_opps = sorted(rows, key=lambda r: float(r.get("valor_global") or 0), reverse=True)[:5]
    top_opportunities = [
        {
            "objeto": r.get("objeto_contrato", "")[:100],
            "orgao": r.get("orgao_nome", ""),
            "valor": float(r.get("valor_global") or 0),
            "data": r.get("data_assinatura", ""),
        }
        for r in top_opps
    ]

    # Top winners
    by_supplier: dict = {}
    for row in rows:
        cnpj = row.get("ni_fornecedor") or ""
        if not cnpj:
            continue
        valor = float(row.get("valor_global") or 0)
        if cnpj not in by_supplier:
            by_supplier[cnpj] = {
                "cnpj": cnpj,
                "nome": row.get("nome_fornecedor") or cnpj,
                "total": 0.0,
                "count": 0,
            }
        by_supplier[cnpj]["total"] += valor
        by_supplier[cnpj]["count"] += 1

    top_winners_data = sorted(by_supplier.values(), key=lambda x: x["total"], reverse=True)[:10]
    top_winners = [
        {"nome": w["nome"], "cnpj": w["cnpj"], "total": round(w["total"], 2), "contratos": w["count"]}
        for w in top_winners_data
    ]

    return {
        "sector_id": sector_id,
        "sector_name": sector_name,
        "period": period,
        "total_licitacoes": total_licitacoes,
        "total_value": round(total_value, 2),
        "avg_value": round(avg_value, 2),
        "top_opportunities": top_opportunities,
        "top_winners": top_winners,
        "executive_summary": (
            f"No período, o setor de {sector_name} registrou {total_licitacoes} contratos "
            f"no valor total de R$ {total_value:,.2f}. "
            f"Valor médio por contrato: R$ {avg_value:,.2f}."
        ),
        "sample_pdf_available": True,
    }
