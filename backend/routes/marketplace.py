"""MKT-001 (#1616): Subcontract Marketplace routes.

Public + authenticated endpoints for the subcontract marketplace MVP:

- GET /v1/marketplace/opportunities — list open opportunities (auth required)
- POST /v1/marketplace/express-interest — express interest in an opportunity
- POST /v1/marketplace/contact/{opportunity_id} — reveal contact (Insight+ gate)

Feature flag: SUBCONTRACT_MARKETPLACE_ENABLED (default true).
When disabled, all endpoints return 404.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_auth
from database import get_db
from schemas.marketplace import (
    ContactRevealResponse,
    ExpressInterestRequest,
    ExpressInterestResponse,
    SubcontractOpportunity,
    SubcontractOpportunityResponse,
)
from supabase_client import sb_execute

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/marketplace",
    tags=["marketplace"],
)


def _marketplace_enabled() -> None:
    """Check if marketplace feature is enabled."""
    try:
        from config.features import get_feature_flag
        if not get_feature_flag("SUBCONTRACT_MARKETPLACE_ENABLED"):
            raise HTTPException(
                status_code=404,
                detail="Marketplace de subcontratação não está disponível no momento.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("MKT-001: Feature flag check failed: %s", e)


# ---------------------------------------------------------------------------
# GET /v1/marketplace/opportunities
# ---------------------------------------------------------------------------


@router.get(
    "/opportunities",
    response_model=SubcontractOpportunityResponse,
    summary="Listar oportunidades de subcontratação",
    description=(
        "Retorna oportunidades abertas de subcontratação. "
        "Filtrável por setor e UF. Paginação padrão: 20 itens."
    ),
)
async def list_opportunities(
    setor: Optional[str] = Query(None, description="Filtrar por setor"),
    uf: Optional[str] = Query(None, description="Filtrar por UF"),
    page: int = Query(default=1, ge=1, description="Número da página"),
    page_size: int = Query(default=20, ge=1, le=100, description="Itens por página"),
    user=Depends(require_auth),
    db=Depends(get_db),
):
    """List open subcontract opportunities with optional filters."""
    _marketplace_enabled()

    try:
        # Build query
        query = (
            db.table("subcontract_opportunities")
            .select("*", count="exact")
            .eq("status", "open")
            .order("created_at", desc=True)
        )

        if setor:
            query = query.eq("sector", setor)
        if uf:
            query = query.eq("uf", uf.upper())

        # Pagination
        offset = (page - 1) * page_size
        query = query.range(offset, offset + page_size - 1)

        result = await sb_execute(query, category="read")
        opportunities_data = result.data or []
        total = result.count or 0

        # Enrich with interest count for each opportunity
        opportunities = []
        for opp in opportunities_data:
            interest_count = await _get_interest_count(db, opp["id"])
            opportunities.append(SubcontractOpportunity(
                id=opp["id"],
                contract_id=opp.get("contract_id"),
                winner_cnpj=opp["winner_cnpj"],
                winner_name=opp.get("winner_name"),
                sector=opp.get("sector"),
                value=float(opp["value"]) if opp.get("value") else None,
                services_needed=opp.get("services_needed", []) or [],
                status=opp.get("status", "open"),
                uf=opp.get("uf"),
                municipio=opp.get("municipio"),
                orgao_nome=opp.get("orgao_nome"),
                objeto=opp.get("objeto"),
                discovery_reason=opp.get("discovery_reason"),
                created_at=opp["created_at"],
                interest_count=interest_count,
            ))

        total_pages = max(1, (total + page_size - 1) // page_size)

        return SubcontractOpportunityResponse(
            opportunities=opportunities,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("MKT-001: Failed to list opportunities: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Erro ao listar oportunidades de subcontratação.",
        )


# ---------------------------------------------------------------------------
# POST /v1/marketplace/express-interest
# ---------------------------------------------------------------------------


@router.post(
    "/express-interest",
    response_model=ExpressInterestResponse,
    summary="Demonstrar interesse em oportunidade",
    description=(
        "Registra o interesse do usuário autenticado em uma oportunidade "
        "de subcontratação. Cada usuário pode se interessar uma única vez "
        "por oportunidade."
    ),
)
async def express_interest(
    body: ExpressInterestRequest,
    user=Depends(require_auth),
    db=Depends(get_db),
):
    """Register user interest in a subcontract opportunity."""
    _marketplace_enabled()

    user_id = user.get("sub") or user.get("id", "")

    try:
        # Verify opportunity exists and is open
        opp_result = await sb_execute(
            db.table("subcontract_opportunities")
            .select("id, status")
            .eq("id", body.opportunity_id)
            .limit(1)
        )
        if not opp_result.data:
            raise HTTPException(
                status_code=404,
                detail="Oportunidade não encontrada.",
            )

        opportunity = opp_result.data[0]
        if opportunity.get("status") != "open":
            raise HTTPException(
                status_code=400,
                detail="Esta oportunidade não está mais disponível.",
            )

        # Insert interest
        insert_data = {
            "opportunity_id": body.opportunity_id,
            "user_id": user_id,
        }
        if body.message:
            insert_data["message"] = body.message

        await sb_execute(
            db.table("subcontract_interests").insert(insert_data),
            category="write",
        )

        logger.info(
            "MKT-001: Interest expressed — user=%s, opportunity=%s",
            user_id, body.opportunity_id,
        )

        return ExpressInterestResponse(
            success=True,
            message="Interesse registrado com sucesso. O vencedor do contrato será notificado.",
        )
    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e).lower()
        if "unique" in error_str or "duplicate" in error_str:
            raise HTTPException(
                status_code=409,
                detail="Você já demonstrou interesse nesta oportunidade.",
            )
        logger.error("MKT-001: Failed to express interest: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Erro ao registrar interesse.",
        )


# ---------------------------------------------------------------------------
# POST /v1/marketplace/contact/{opportunity_id}
# ---------------------------------------------------------------------------


@router.post(
    "/contact/{opportunity_id}",
    response_model=ContactRevealResponse,
    summary="Revelar dados de contato (Insight+)",
    description=(
        "Revela dados de contato do vencedor do contrato. "
        "Gate: plano Insight+ ou superior. "
        "Usuários em plano gratuito ou trial recebem upgrade prompt."
    ),
)
async def reveal_contact(
    opportunity_id: str,
    user=Depends(require_auth),
    db=Depends(get_db),
):
    """Reveal winner contact details for Insight+ users."""
    _marketplace_enabled()

    user_id = user.get("sub") or user.get("id", "")

    # Check plan gate — Insight+ required
    plan_type = user.get("plan_type", "free_trial")
    insight_plus_plans = {"smartlic_pro", "consultoria", "founder", "insight_plus", "enterprise"}

    if plan_type not in insight_plus_plans:
        raise HTTPException(
            status_code=402,
            detail=(
                "Dados de contato disponíveis apenas no plano Insight+. "
                "Acesse /planos para fazer upgrade."
            ),
        )

    try:
        # Fetch opportunity with contract details
        opp_result = await sb_execute(
            db.table("subcontract_opportunities")
            .select("*")
            .eq("id", opportunity_id)
            .limit(1)
        )
        if not opp_result.data:
            raise HTTPException(
                status_code=404,
                detail="Oportunidade não encontrada.",
            )

        opp = opp_result.data[0]

        # Fetch winner contact info from enriched_entities if available
        winner_cnpj = opp.get("winner_cnpj", "")
        winner_name = opp.get("winner_name", "")
        winner_email = None
        winner_phone = None

        try:
            entity_result = await sb_execute(
                db.table("enriched_entities")
                .select("email, telefone")
                .eq("cnpj", winner_cnpj)
                .limit(1)
            )
            if entity_result.data:
                entity = entity_result.data[0]
                winner_email = entity.get("email")
                winner_phone = entity.get("telefone")
        except Exception:
            logger.debug("MKT-001: enriched_entities lookup failed for %s", winner_cnpj)

        logger.info(
            "MKT-001: Contact revealed — user=%s, opportunity=%s, winner=%s",
            user_id, opportunity_id, winner_cnpj,
        )

        return ContactRevealResponse(
            winner_cnpj=winner_cnpj,
            winner_name=winner_name,
            winner_email=winner_email,
            winner_phone=winner_phone,
            contract_value=float(opp["value"]) if opp.get("value") else None,
            orgao_nome=opp.get("orgao_nome"),
            message="Dados de contato liberados — plano Insight+",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("MKT-001: Failed to reveal contact: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Erro ao buscar dados de contato.",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_interest_count(db, opportunity_id: str) -> int:
    """Get the count of interests for an opportunity."""
    try:
        result = await sb_execute(
            db.table("subcontract_interests")
            .select("id", count="exact")
            .eq("opportunity_id", opportunity_id)
        )
        return result.count if result.count else 0
    except Exception:
        return 0
