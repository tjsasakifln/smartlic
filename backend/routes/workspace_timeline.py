"""Workspace Timeline routes (B2GOPS-014 / #2024).

Provides endpoints for reading and creating timeline events per edital,
enabling a chronological feed of events for the workspace.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_auth
from supabase_client import get_supabase, sb_execute
from schemas.workspace_timeline import (
    TimelineEventoCreate,
    TimelineResponse,
    VALID_TIMELINE_TIPOS,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspace-timeline"])

# Only nota_manual and lembrete can be created manually by the user
MANUAL_CREATION_TIPOS = {"nota_manual", "lembrete"}

# Default pagination
_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200


def _row_to_evento(row: dict) -> dict:
    """Convert a Supabase row to a serializable event dict."""
    return {
        "id": row["id"],
        "edital_id": row["edital_id"],
        "user_id": row["user_id"],
        "tipo": row["tipo"],
        "titulo": row["titulo"],
        "descricao": row.get("descricao"),
        "critico": row.get("critico", False),
        "metadata": row.get("metadata", {}),
        "created_at": row["created_at"],
    }


@router.get(
    "/workspace/timeline/{edital_id}",
    response_model=TimelineResponse,
    summary="Listar eventos da timeline de um edital",
    description=(
        "Retorna eventos cronológicos de um edital em ordem DESC. "
        "Suporta filtros por tipo_evento, data_inicio, data_fim, critico. "
        "Paginação via limit (default 50, max 200) e offset."
    ),
)
async def list_timeline_eventos(
    edital_id: str,
    tipo_evento: Optional[str] = Query(
        default=None,
        description="Filtrar por tipo de evento (ex: publicacao, alteracao)",
    ),
    data_inicio: Optional[str] = Query(
        default=None,
        description="Filtrar eventos a partir desta data (ISO 8601)",
    ),
    data_fim: Optional[str] = Query(
        default=None,
        description="Filtrar eventos até esta data (ISO 8601)",
    ),
    critico: Optional[bool] = Query(
        default=None,
        description="Filtrar apenas eventos críticos",
    ),
    limit: int = Query(
        default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT,
        description="Número máximo de eventos por página",
    ),
    offset: int = Query(
        default=0, ge=0,
        description="Offset para paginação",
    ),
    user: dict = Depends(require_auth),
) -> TimelineResponse:
    """List timeline events for an edital, ordered chronologically DESC."""
    user_id = user["id"]
    supabase = get_supabase()

    try:
        # Build base query for the user-scoped client (RLS handles user_id)
        query = (
            supabase.table("workspace_timeline_eventos")
            .select("*", count="exact")
            .eq("edital_id", edital_id)
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )

        # Apply optional filters
        if tipo_evento:
            if tipo_evento not in VALID_TIMELINE_TIPOS:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "message": (
                            f"Tipo de evento inválido: '{tipo_evento}'. "
                            f"Valores válidos: {sorted(VALID_TIMELINE_TIPOS)}"
                        ),
                        "error_code": "invalid_tipo_evento",
                    },
                )
            query = query.eq("tipo", tipo_evento)

        if data_inicio:
            query = query.gte("created_at", data_inicio)

        if data_fim:
            query = query.lte("created_at", data_fim)

        if critico is not None:
            query = query.eq("critico", critico)

        # Execute with pagination
        query = query.range(offset, offset + limit - 1)
        result = await sb_execute(query)

        eventos_data = result.data or []
        total = result.count if hasattr(result, "count") else len(eventos_data)

        eventos = [_row_to_evento(e) for e in eventos_data]

        return TimelineResponse(
            eventos=eventos,
            total=total,
            limit=limit,
            offset=offset,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to list timeline eventos for edital=%s user=%s",
            edital_id, user_id,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Erro ao listar eventos da timeline.",
                "error_code": "timeline_list_error",
            },
        ) from exc


@router.post(
    "/workspace/timeline/{edital_id}/evento",
    status_code=201,
    summary="Criar evento manual na timeline",
    description=(
        "Cria um evento manual na timeline do edital. "
        "Apenas tipos 'nota_manual' e 'lembrete' são permitidos."
    ),
)
async def create_timeline_evento(
    edital_id: str,
    body: TimelineEventoCreate,
    user: dict = Depends(require_auth),
) -> dict:
    """Create a manual timeline event (nota_manual or lembrete)."""
    user_id = user["id"]

    # Validate tipo — only manual creation tipos are allowed
    if body.tipo not in MANUAL_CREATION_TIPOS:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    f"Tipo '{body.tipo}' não pode ser criado manualmente. "
                    f"Tipos permitidos: {sorted(MANUAL_CREATION_TIPOS)}"
                ),
                "error_code": "tipo_nao_permitido",
            },
        )

    supabase = get_supabase()

    # Determine if lembrete is always critico
    is_critico = body.tipo == "lembrete"

    try:
        insert_data = {
            "edital_id": edital_id,
            "user_id": user_id,
            "tipo": body.tipo,
            "titulo": body.titulo,
            "descricao": body.descricao,
            "critico": is_critico,
            "metadata": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        result = await sb_execute(
            supabase.table("workspace_timeline_eventos")
            .insert(insert_data)
        )

        if not result.data:
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Erro ao criar evento na timeline.",
                    "error_code": "timeline_create_error",
                },
            )

        created = query.data[0]
        return _row_to_evento(created)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "Failed to create timeline evento for edital=%s user=%s",
            edital_id, user_id,
        )
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Erro ao criar evento na timeline.",
                "error_code": "timeline_create_error",
            },
        ) from exc
