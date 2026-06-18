"""B2GOPS-011 (#2021): Workspace watchlist CRUD.

Endpoints:
  - GET    /v1/workspace/watchlist      — List watchlist items
  - POST   /v1/workspace/watchlist      — Add edital to watchlist
  - DELETE /v1/workspace/watchlist/{id} — Remove from watchlist
"""

import logging

from fastapi import APIRouter, Depends, HTTPException

from auth import require_auth
from log_sanitizer import mask_user_id
from schemas.common import SuccessMessageResponse
from schemas.workspace_alertas import (
    WatchlistCreate,
    WatchlistItem,
    WatchlistResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspace"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_watchlist_item(row: dict) -> WatchlistItem:
    """Convert a Supabase row dict into a WatchlistItem."""
    return WatchlistItem(
        id=row["id"],
        user_id=row["user_id"],
        edital_id=row["edital_id"],
        uf=row.get("uf", ""),
        setor=row.get("setor", ""),
        keywords=row.get("keywords") or [],
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# GET /v1/workspace/watchlist — List watchlist items
# ---------------------------------------------------------------------------


@router.get("/workspace/watchlist", response_model=WatchlistResponse)
async def list_watchlist(user: dict = Depends(require_auth)):
    """List all editais in the user's workspace watchlist."""
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("workspace_watchlist")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
        )

        items = [
            _row_to_watchlist_item(row)
            for row in (result.data or [])
        ]

        return WatchlistResponse(items=items, total=len(items))

    except Exception as e:
        logger.error(
            "Error listing watchlist for user %s: %s",
            mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao listar watchlist.")


# ---------------------------------------------------------------------------
# POST /v1/workspace/watchlist — Add edital to watchlist
# ---------------------------------------------------------------------------


@router.post("/workspace/watchlist", response_model=WatchlistItem)
async def add_to_watchlist(
    body: WatchlistCreate,
    user: dict = Depends(require_auth),
):
    """Add an edital to the user's workspace watchlist.

    If the same edital_id already exists for this user, returns
    the existing entry (idempotent).
    """
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        # Check for existing entry (idempotent)
        existing = await sb_execute(
            sb.table("workspace_watchlist")
            .select("*")
            .eq("user_id", user_id)
            .eq("edital_id", body.edital_id)
            .maybe_single()
        )

        if existing.data:
            logger.info(
                "Watchlist entry already exists for edital %s (user %s)",
                body.edital_id[:12], mask_user_id(user_id),
            )
            return _row_to_watchlist_item(existing.data)

        # Insert new entry
        result = await sb_execute(
            sb.table("workspace_watchlist").insert({
                "user_id": user_id,
                "edital_id": body.edital_id,
                "uf": body.uf,
                "setor": body.setor,
                "keywords": body.keywords,
            })
        )

        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=500, detail="Erro ao adicionar à watchlist."
            )

        logger.info(
            "Added edital %s to watchlist for user %s",
            body.edital_id[:12], mask_user_id(user_id),
        )
        return _row_to_watchlist_item(result.data[0])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error adding to watchlist for user %s: %s",
            mask_user_id(user_id), e,
        )
        raise HTTPException(
            status_code=500, detail="Erro ao adicionar à watchlist."
        )


# ---------------------------------------------------------------------------
# DELETE /v1/workspace/watchlist/{id} — Remove from watchlist
# ---------------------------------------------------------------------------


@router.delete(
    "/workspace/watchlist/{watchlist_id}",
    response_model=SuccessMessageResponse,
)
async def remove_from_watchlist(
    watchlist_id: str,
    user: dict = Depends(require_auth),
):
    """Remove an edital from the user's workspace watchlist."""
    from supabase_client import get_supabase, sb_execute

    user_id = user["id"]
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("workspace_watchlist")
            .delete()
            .eq("id", watchlist_id)
            .eq("user_id", user_id)
        )

        if not result.data or len(result.data) == 0:
            raise HTTPException(
                status_code=404, detail="Item da watchlist não encontrado."
            )

        logger.info(
            "Removed watchlist entry %s for user %s",
            watchlist_id[:8], mask_user_id(user_id),
        )
        return {
            "success": True,
            "message": "Item removido da watchlist com sucesso.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error removing watchlist entry %s for user %s: %s",
            watchlist_id[:8], mask_user_id(user_id), e,
        )
        raise HTTPException(
            status_code=500, detail="Erro ao remover da watchlist."
        )
