"""Workspace collaborative hub routes for B2GOPS-010 (#2020).

Provides aggregated endpoints for the workspace flagship page:
  - GET /v1/workspace/editais-hoje   — Today's procurement opportunities (top 10)
  - GET /v1/workspace/resumo         — Aggregated summary counts

All endpoints require authentication.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends

from auth import require_auth
from log_sanitizer import mask_user_id
from schemas.workspace import EditaisHojeResponse, EditaisHojeItem, WorkspaceResumo

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspace"])


@router.get("/workspace/editais-hoje", response_model=EditaisHojeResponse)
async def get_editais_hoje(
    user: dict = Depends(require_auth),
) -> EditaisHojeResponse:
    """Fetch up to 10 procurement opportunities published today.

    Queries `pncp_raw_bids` filtered by current date (UTC) via the
    `search_datalake` RPC. Returns an empty list on transient errors
    (fail-open) instead of blocking the workspace page.
    """
    _ = user  # authenticated — we only verify the user is logged in

    from supabase_client import get_supabase, sb_execute

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        sb = get_supabase()
        result = await sb_execute(
            sb.table("pncp_raw_bids")
            .select("pncp_id, orgao, uf, objeto, valor_estimado, data_publicacao, data_encerramento, link_pncp, modalidade, numero_compra")
            .gte("data_publicacao", today)
            .lt("data_publicacao", f"{today}T23:59:59")
            .order("data_publicacao", desc=True)
            .limit(10)
        )

        rows = result.data or []
        items = [_row_to_editais_item(row) for row in rows]

        return EditaisHojeResponse(items=items, total=len(items))

    except Exception as e:
        logger.warning(
            "Error fetching today's editais for user %s (fail-open): %s",
            mask_user_id(user["id"]), e,
        )
        return EditaisHojeResponse(items=[], total=0)


@router.get("/workspace/resumo", response_model=WorkspaceResumo)
async def get_workspace_resumo(
    user: dict = Depends(require_auth),
) -> WorkspaceResumo:
    """Aggregated counts for the workspace dashboard widgets.

    Returns the number of:
      - editais published today
      - pipeline items belonging to the user
      - pipeline items with deadlines within 7 days
      - unread alerts

    All sources fail-open: transient errors return 0 for that counter
    instead of failing the entire response.
    """
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    now_iso = datetime.now(timezone.utc).isoformat()
    deadline_7d = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    editais_hoje_count = 0
    pipeline_count = 0
    pipeline_prazo_proximo = 0
    alerts_unread_count = 0

    # --- Fetch editais_hoje_count ---
    try:
        count_result = await sb_execute(
            sb.table("pncp_raw_bids")
            .select("pncp_id", count="exact")
            .gte("data_publicacao", today)
            .lt("data_publicacao", f"{today}T23:59:59")
            .limit(1)
        )
        editais_hoje_count = count_result.count if count_result.count is not None else 0
    except Exception as e:
        logger.warning(
            "Error counting today's editais for user %s (fail-open): %s",
            mask_user_id(user_id), e,
        )

    # --- Fetch pipeline_count ---
    try:
        pipe_result = await sb_execute(
            sb.table("pipeline_items")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .limit(1)
        )
        pipeline_count = pipe_result.count if pipe_result.count is not None else 0
    except Exception as e:
        logger.warning(
            "Error counting pipeline items for user %s (fail-open): %s",
            mask_user_id(user_id), e,
        )

    # --- Fetch pipeline_prazo_proximo (deadline within 7d) ---
    try:
        prazo_result = await sb_execute(
            sb.table("pipeline_items")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("data_encerramento", now_iso)
            .lte("data_encerramento", deadline_7d)
            .limit(1)
        )
        pipeline_prazo_proximo = prazo_result.count if prazo_result.count is not None else 0
    except Exception as e:
        logger.warning(
            "Error counting upcoming deadlines for user %s (fail-open): %s",
            mask_user_id(user_id), e,
        )

    # --- Fetch alerts_unread_count ---
    try:
        alerts_result = await sb_execute(
            sb.table("user_alerts")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .eq("is_read", False)
            .limit(1)
        )
        alerts_unread_count = alerts_result.count if alerts_result.count is not None else 0
    except Exception as e:
        logger.warning(
            "Error counting unread alerts for user %s (fail-open): %s",
            mask_user_id(user_id), e,
        )

    return WorkspaceResumo(
        editais_hoje_count=editais_hoje_count,
        pipeline_count=pipeline_count,
        pipeline_prazo_proximo=pipeline_prazo_proximo,
        alerts_unread_count=alerts_unread_count,
    )


def _row_to_editais_item(row: dict) -> EditaisHojeItem:
    """Convert a Supabase row from pncp_raw_bids into an EditaisHojeItem."""
    return EditaisHojeItem(
        pncp_id=row.get("pncp_id"),
        orgao=row.get("orgao"),
        uf=row.get("uf"),
        objeto=row.get("objeto"),
        valor_estimado=_safe_float(row.get("valor_estimado")),
        data_publicacao=row.get("data_publicacao"),
        data_encerramento=row.get("data_encerramento"),
        link_pncp=row.get("link_pncp"),
        modalidade=row.get("modalidade"),
        numero_compra=row.get("numero_compra"),
    )


def _safe_float(value: object) -> float | None:
    """Safely convert a value to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None
