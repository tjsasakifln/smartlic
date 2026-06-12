"""WIDGET-COMPINT-001: Competitive Intelligence embeddable widget endpoint.

Public endpoint (no auth) returning market data aggregated from
pncp_supplier_contracts. Supports 4 themes and cross-origin embedding.

Rate limit: 100 req/min per IP.
Cache: Redis 1h TTL.
CORS: Allow all origins (widget is embedded cross-origin).
"""

from __future__ import annotations

import json
import logging
import time as time_mod
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from supabase_client import get_supabase, sb_execute

from schemas.competitive_intel import (
    FornecedorShare,
    MarketShareData,
    MesSerie,
    MonthlyTrendData,
    OrgaoItem,
    OrgaoRankingData,
    THEME_TYPES,
    TopWinnersData,
    WinnerItem,
)
from sectors import SECTORS

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["competitive_intel"],
)

# 1h cache TTL
_CACHE_TTL_SECONDS = 60 * 60
_WINDOW_MONTHS_DEFAULT = 12
_DEFAULT_LIMIT = 5


# ---------------------------------------------------------------------------
# CORS helpers for cross-origin embedding
# ---------------------------------------------------------------------------


def _build_cors_response(data: dict, status_code: int = 200) -> JSONResponse:
    """Build a JSON response with permissive CORS headers.

    The widget needs to be embeddable on any external site via iframe,
    so we allow all origins.
    """
    resp = JSONResponse(content=data, status_code=status_code)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Max-Age"] = "86400"
    resp.headers["Cache-Control"] = (
        f"public, max-age={_CACHE_TTL_SECONDS}, stale-while-revalidate=300"
    )
    resp.headers["Vary"] = "Origin"
    return resp


# ---------------------------------------------------------------------------
# Cache helpers (Redis + InMemory fallback)
# ---------------------------------------------------------------------------

_widget_cache: dict[str, tuple[dict, float]] = {}


async def _get_cached(key: str) -> Optional[dict]:
    """Try Redis first, then InMemory fallback."""
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is not None:
            raw = await redis.get(f"widget_compint:{key}")
            if raw:
                return json.loads(raw)
    except Exception as e:
        logger.debug("competitive_intel: Redis cache read failed: %s", e)

    # InMemory fallback
    entry = _widget_cache.get(key)
    if entry:
        data, ts = entry
        if time_mod.time() - ts < _CACHE_TTL_SECONDS:
            return data
        _widget_cache.pop(key, None)

    return None


async def _set_cached(key: str, data: dict) -> None:
    """Set cache in Redis and InMemory."""
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is not None:
            await redis.setex(
                f"widget_compint:{key}",
                _CACHE_TTL_SECONDS,
                json.dumps(data, default=str),
            )
    except Exception as e:
        logger.debug("competitive_intel: Redis cache write failed: %s", e)

    # InMemory always
    _widget_cache[key] = (data, time_mod.time())


# ---------------------------------------------------------------------------
# Data computation helpers
# ---------------------------------------------------------------------------


def _compute_hhi(fornecedores: list[dict], total_value: float) -> str:
    """Compute Herfindahl-Hirschman Index concentration level.

    HHI < 1500 = Baixa, 1500-2500 = Media, > 2500 = Alta.
    """
    if total_value <= 0 or not fornecedores:
        return "Baixa"
    hhi = sum(
        (f["valor_total"] / total_value * 100) ** 2
        for f in fornecedores
        if f.get("valor_total")
    )
    if hhi >= 2500:
        return "Alta"
    if hhi >= 1500:
        return "Media"
    return "Baixa"


def _compute_trend(serie: list[dict]) -> str:
    """Determine trend direction from the monthly time series.

    Compares the last 3 months average vs the period before.
    """
    if len(serie) < 4:
        return "estavel"

    sorted_serie = sorted(serie, key=lambda x: x.get("mes", ""))
    recent = [s["valor_total"] for s in sorted_serie[-3:] if s.get("valor_total")]
    earlier = [s["valor_total"] for s in sorted_serie[:-3] if s.get("valor_total")]

    if not recent or not earlier:
        return "estavel"

    recent_avg = sum(recent) / len(recent)
    earlier_avg = sum(earlier) / len(earlier)

    if earlier_avg <= 0:
        return "estavel"

    change = (recent_avg - earlier_avg) / earlier_avg
    if change > 0.10:
        return "crescimento"
    if change < -0.10:
        return "queda"
    return "estavel"


def _build_market_share(rpc_data: dict, limit: int = _DEFAULT_LIMIT) -> MarketShareData:
    """Build market-share response from RPC data."""
    fornecedores = rpc_data.get("top_fornecedores", [])
    total_value = float(rpc_data.get("total_value", 0))
    total_contracts = int(rpc_data.get("total_contracts", 0))

    top = []
    for f in fornecedores[:limit]:
        f_valor = float(f.get("valor_total", 0))
        percentual = (f_valor / total_value * 100) if total_value > 0 else 0
        top.append(
            FornecedorShare(
                nome=f.get("nome_fornecedor", "N/D"),
                cnpj=f.get("ni_fornecedor", ""),
                percentual=round(percentual, 1),
                valor=f_valor,
                contratos=int(f.get("count", 0)),
            )
        )

    return MarketShareData(
        valor_total=total_value,
        total_contratos=total_contracts,
        top_fornecedores=top,
        concentracao=_compute_hhi(fornecedores, total_value),
    )


def _build_top_winners(rpc_data: dict, limit: int = _DEFAULT_LIMIT) -> TopWinnersData:
    """Build top-winners response from RPC data."""
    fornecedores = rpc_data.get("top_fornecedores", [])

    winners = []
    for f in fornecedores[:limit]:
        winners.append(
            WinnerItem(
                nome=f.get("nome_fornecedor", "N/D"),
                cnpj=f.get("ni_fornecedor", ""),
                contratos=int(f.get("count", 0)),
                valor_total=float(f.get("valor_total", 0)),
                crescimento=None,
            )
        )

    return TopWinnersData(winners=winners)


def _build_monthly_trend(rpc_data: dict) -> MonthlyTrendData:
    """Build monthly-trend response from RPC data."""
    serie_raw = rpc_data.get("serie_temporal", [])

    serie = []
    for s in serie_raw:
        serie.append(
            MesSerie(
                mes=s.get("mes", ""),
                valor=float(s.get("valor_total", 0)),
                contratos=int(s.get("count", 0)),
            )
        )

    return MonthlyTrendData(
        serie=serie,
        tendencia=_compute_trend(serie_raw),
    )


def _build_orgao_ranking(rpc_data: dict, limit: int = _DEFAULT_LIMIT) -> OrgaoRankingData:
    """Build orgao-ranking response from RPC data."""
    orgaos_raw = rpc_data.get("top_orgaos", [])

    orgaos = []
    for o in orgaos_raw[:limit]:
        orgaos.append(
            OrgaoItem(
                nome=o.get("orgao_nome", "N/D"),
                cnpj=o.get("orgao_cnpj", ""),
                valor=float(o.get("valor_total", 0)),
                contratos=int(o.get("count", 0)),
            )
        )

    return OrgaoRankingData(orgaos=orgaos)


# ---------------------------------------------------------------------------
# Rate limit helper
# ---------------------------------------------------------------------------


async def _check_rate_limit(request: Request) -> None:
    """Apply rate limiting: 100 req/min per IP. Fail-open."""
    try:
        from rate_limiter import rate_limiter as _rl

        ip = request.headers.get("X-Forwarded-For", "").split(",")[-1].strip()
        if not ip:
            ip = request.client.host if request.client else "unknown"

        key = f"rl_widget:ip:{ip}"
        allowed, retry_after = await _rl.check_rate_limit(key, 100)

        if not allowed:
            retry_sec = int(retry_after) if retry_after else 60
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "retry_after_sec": retry_sec,
                },
                headers={
                    "Retry-After": str(retry_sec),
                    "Access-Control-Allow-Origin": "*",
                },
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.debug("competitive_intel: rate limit check failed (fail-open): %s", e)


# ---------------------------------------------------------------------------
# OPTIONS handler for CORS preflight
# ---------------------------------------------------------------------------


@router.options("/widget/competitive-intel")
async def widget_competitive_intel_options():
    """Handle CORS preflight requests."""
    resp = JSONResponse(content={})
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Max-Age"] = "86400"
    return resp


# ---------------------------------------------------------------------------
# Main endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/widget/competitive-intel",
    summary="Dados de Inteligencia Competitiva para Widget Embedavel",
    description=(
        "Retorna dados agregados de contratos publicos por setor para widget embedavel.\n\n"
        "Temas:\n"
        "- market-share: Market share dos fornecedores no setor\n"
        "- top-winners: Top vencedores com indicadores de crescimento\n"
        "- monthly-trend: Tendencia mensal de contratos\n"
        "- orgao-ranking: Ranking de orgaos compradores"
    ),
    response_model=None,  # We build response manually for CORS + cache headers
)
async def widget_competitive_intel(
    request: Request,
    setor: str = Query(..., description="ID do setor (ex: ti, saude, construcao)"),
    tema: str = Query(
        ...,
        description="Tema: market-share | top-winners | monthly-trend | orgao-ranking",
    ),
    uf: Optional[str] = Query(default=None, description="UF (2 letras, opcional)"),
    limit: int = Query(
        default=_DEFAULT_LIMIT,
        description="Limite de itens na resposta (max 20)",
        ge=1,
        le=20,
    ),
):
    # --- Validate tema
    tema_lower = tema.lower()
    if tema_lower not in THEME_TYPES:
        return _build_cors_response(
            {
                "error": "invalid_tema",
                "message": (
                    f"Tema invalido: '{tema}'. "
                    f"Valores aceitos: {', '.join(sorted(THEME_TYPES))}"
                ),
            },
            status_code=400,
        )

    # --- Validate setor
    sector_config = SECTORS.get(setor)
    if sector_config is None:
        valid_sectors = list(SECTORS.keys())
        return _build_cors_response(
            {
                "error": "invalid_setor",
                "message": (
                    f"Setor invalido: '{setor}'. "
                    f"Setores validos: {', '.join(valid_sectors)}"
                ),
            },
            status_code=400,
        )

    # --- Validate UF
    if uf is not None:
        uf_clean = uf.strip().upper()
        if len(uf_clean) != 2 or not uf_clean.isalpha():
            return _build_cors_response(
                {
                    "error": "invalid_uf",
                    "message": "UF deve ter 2 letras (ex: SP, RJ, MG)",
                },
                status_code=400,
            )
    else:
        uf_clean = None

    # --- Rate limit
    await _check_rate_limit(request)

    # --- Cache key
    cache_key = f"{setor}:{uf_clean or 'BR'}:{tema_lower}:limit={limit}"

    # --- Check cache
    cached = await _get_cached(cache_key)
    if cached:
        return _build_cors_response(cached)

    # --- Fetch data from RPC
    try:
        keywords = list(sector_config.keywords)
        sb = get_supabase()
        rpc_result = await sb_execute(
            sb.rpc(
                "widget_competitive_intel",
                {
                    "p_sector": setor,
                    "p_keywords": keywords,
                    "p_uf": uf_clean or "",
                    "p_window_months": _WINDOW_MONTHS_DEFAULT,
                },
            ),
            category="rpc",
        )
        rpc_data = rpc_result.data if hasattr(rpc_result, "data") else rpc_result
    except Exception as e:
        logger.error("competitive_intel: RPC failed for setor=%s uf=%s: %s", setor, uf_clean, e)
        return _build_cors_response(
            {
                "error": "data_unavailable",
                "message": "Dados temporariamente indisponiveis. Tente novamente em instantes.",
            },
            status_code=503,
        )

    # --- Build response by theme
    sector_name = sector_config.name
    period_label = f"Ultimos {_WINDOW_MONTHS_DEFAULT} meses"

    if tema_lower == "market-share":
        dados = _build_market_share(rpc_data, limit=limit)
    elif tema_lower == "top-winners":
        dados = _build_top_winners(rpc_data, limit=limit)
    elif tema_lower == "monthly-trend":
        dados = _build_monthly_trend(rpc_data)
    elif tema_lower == "orgao-ranking":
        dados = _build_orgao_ranking(rpc_data, limit=limit)
    else:
        return _build_cors_response(
            {"error": "invalid_tema"},
            status_code=400,
        )

    response_data = {
        "tema": tema_lower,
        "setor": sector_name,
        "uf": uf_clean,
        "periodo": period_label,
        "dados": dados.model_dump(),
    }

    # --- Cache
    await _set_cached(cache_key, response_data)

    # --- Return
    return _build_cors_response(response_data)
