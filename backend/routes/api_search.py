"""API-SELF-002: API Key authenticated search endpoint.

Endpoints:
    GET /v1/api/search — search via X-API-Key auth header

Reuses the same ``SearchPipeline`` as ``POST /buscar`` but authenticated
with an API key (``require_api_key``) instead of JWT (``require_auth``).

Rate limiting:
    - ``X-RateLimit-Limit``: 100 requests/day (hardcoded for now)
    - ``X-RateLimit-Remaining``: remaining quota in current window
    - Redis key ``ratelimit:api:{user_id}:{YYYY-MM-DD}`` with 24h TTL
    - Returns 429 when exceeded
"""

from __future__ import annotations

import logging
import time as _time
from datetime import datetime, timedelta, timezone
from typing import Optional
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from auth import require_api_key
from schemas import BuscaRequest, BuscaResponse
from search_pipeline import SearchPipeline
from search_context import SearchContext
from config import ENABLE_NEW_PRICING
from pncp_client import PNCPClient, buscar_todas_ufs_paralelo
from filter import (
    aplicar_todos_filtros,
    KEYWORDS_EXCLUSAO,
    KEYWORDS_UNIFORMES,
    match_keywords,
    validate_terms,
)
from excel import create_excel
from rate_limiter import rate_limiter
from authorization import check_user_roles

logger = logging.getLogger(__name__)

router = APIRouter(tags=["api"])

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_RATE_LIMIT_PER_DAY: int = 100  # Hardcoded; configurable per tier in API-SELF-003
_RATE_LIMIT_REDIS_PREFIX: str = "ratelimit:api:"


# ---------------------------------------------------------------------------
# Rate limit helpers
# ---------------------------------------------------------------------------


async def _check_api_rate_limit(
    user_id: str,
    *,
    limit: int = API_RATE_LIMIT_PER_DAY,
) -> tuple[int, int]:
    """Check and enforce daily rate limit for an API key user.

    Redis key format: ``ratelimit:api:{user_id}:{YYYY-MM-DD}``, TTL 24h.
    Falls back to in-memory when Redis is unavailable (fail-open).

    Returns:
        ``(remaining, limit)`` tuple.

    Raises:
        HTTPException 429: when quota is exhausted.
    """
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    redis_key = f"{_RATE_LIMIT_REDIS_PREFIX}{user_id}:{date_str}"

    from redis_pool import get_redis_pool
    redis = await get_redis_pool()

    if redis is not None:
        try:
            count = await redis.incr(redis_key)
            if count == 1:
                await redis.expire(redis_key, 86400)  # 24 hours

            remaining = max(0, limit - count)
            if count > limit:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "detail": "Rate limit exceeded. Try again later.",
                        "retry_after_seconds": 86400,
                    },
                    headers={
                        "X-RateLimit-Limit": str(limit),
                        "X-RateLimit-Remaining": "0",
                        "Retry-After": "86400",
                    },
                )
            return remaining, limit
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("API rate limit Redis error (fail-open): %s", exc)
            return limit, limit  # Fail-open

    # No Redis — allow through (best-effort rate limiting)
    return limit, limit


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/api/search", response_model=BuscaResponse)
async def api_search(
    raw_request: Request,
    http_response: Response,
    q: str = Query(
        ...,
        min_length=2,
        max_length=500,
        description="Search query (keywords or free text)",
    ),
    uf: Optional[str] = Query(
        default=None,
        min_length=2,
        max_length=2,
        description="State (UF) code, e.g. 'SP'. Searches all UFs when omitted.",
    ),
    modalidade: Optional[str] = Query(
        default=None,
        description="Comma-separated modality codes, e.g. '5,6'. Defaults to standard modalities [4,5,6,7] when omitted.",
    ),
    pagina: int = Query(
        default=1,
        ge=1,
        description="Page number (1-indexed). Default: 1.",
    ),
    tamanho: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Items per page (1-100). Default: 20.",
    ),
    _api_user_id: str = Depends(require_api_key),
):
    """Search licitacoes via API key authentication.

    Same search pipeline as ``POST /buscar`` but authenticated with an
    ``X-API-Key`` header instead of JWT Bearer token.

    **Rate limiting:** 100 requests/day per API key (``X-RateLimit-*`` headers).
    """
    # ---- Rate limit check ----
    remaining, limit = await _check_api_rate_limit(_api_user_id)
    http_response.headers["X-RateLimit-Limit"] = str(limit)
    http_response.headers["X-RateLimit-Remaining"] = str(remaining)

    # ---- Build BuscaRequest from query params ----
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    uf_list: list[str] = [uf.upper()] if uf else ["SP"]
    modalidade_list: Optional[list[int]] = (
        [int(m.strip()) for m in modalidade.split(",") if m.strip()]
        if modalidade
        else None
    )

    busca_request = BuscaRequest(
        ufs=uf_list,
        data_inicial=thirty_days_ago,
        data_final=today,
        termos_busca=q,
        modalidades=modalidade_list,
        pagina=pagina,
        itens_por_pagina=tamanho,
    )

    # ---- Build user dict for pipeline ----
    user: dict = {
        "id": _api_user_id,
        "email": f"api-key-{_api_user_id[:8]}@api.smartlic.tech",
        "plan_type": "smartlic_pro",
        "role": "authenticated",
        "aal": "aal1",
    }

    # ---- Build deps namespace (same module-level imports as search/__init__) ----

    deps = SimpleNamespace(
        ENABLE_NEW_PRICING=ENABLE_NEW_PRICING,
        PNCPClient=PNCPClient,
        buscar_todas_ufs_paralelo=buscar_todas_ufs_paralelo,
        aplicar_todos_filtros=aplicar_todos_filtros,
        create_excel=create_excel,
        rate_limiter=rate_limiter,
        check_user_roles=check_user_roles,
        match_keywords=match_keywords,
        KEYWORDS_UNIFORMES=KEYWORDS_UNIFORMES,
        KEYWORDS_EXCLUSAO=KEYWORDS_EXCLUSAO,
        validate_terms=validate_terms,
    )

    ctx = SearchContext(
        request=busca_request,
        user=user,
        start_time=_time.time(),
        tracker=None,
    )

    pipeline = SearchPipeline(deps)

    # ---- Execute pipeline ----
    try:
        response = await pipeline.run(ctx)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "API search pipeline failed for user %s: %s",
            _api_user_id[:8],
            exc,
        )
        raise HTTPException(status_code=500, detail="Search pipeline failed")

    # Defensive fallback (same pattern as buscar_licitacoes)
    if response is None:
        response = ctx.response
    if response is None:
        logger.error(
            "API search pipeline returned None for user %s — building empty response",
            _api_user_id[:8],
        )
        from llm import gerar_resumo_fallback
        response = BuscaResponse(
            resumo=gerar_resumo_fallback(
                [],
                sector_name="licitacoes",
                termos_busca=q,
            ),
            licitacoes=[],
            excel_base64=None,
            excel_available=False,
            quota_used=0,
            quota_remaining=0,
            total_raw=0,
            total_filtrado=0,
            filter_stats={},
            response_state="empty_failure",
        )

    return response
