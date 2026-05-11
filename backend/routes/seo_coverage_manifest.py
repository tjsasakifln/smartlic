"""SEO-COVERAGE-MANIFEST-001: Endpoint público de cobertura de dados para sitemap gate.

GET /v1/seo/coverage-manifest
  Retorna JSON com status de cobertura por entidade.
  Cache: 1h em-memória.
  Público (sem auth) — mesma proteção dos endpoints *_publicos.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import sentry_sdk
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from routes._sitemap_cache_headers import SITEMAP_CACHE_HEADERS

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seo"])

_CACHE_TTL_SECONDS = 3600  # 1h — alinha com ISR frontend
_NEGATIVE_CACHE_TTL_SECONDS = 300  # 5min fallback
_BUDGET_S = 10.0

_manifest_cache: dict[str, tuple[dict, float, float]] = {}


class CoverageEntry(BaseModel):
    coverage_status: str  # full | partial | historical_empty | empty
    last_activity_at: Optional[str] = None
    updated_at: str


class CoverageManifestResponse(BaseModel):
    entities: dict[str, dict[str, CoverageEntry]]  # entity_type → entity_id → entry
    total: int
    generated_at: str


def _get_cached(key: str) -> Optional[dict]:
    if key not in _manifest_cache:
        return None
    data, ts, ttl = _manifest_cache[key]
    if time.time() - ts >= ttl:
        del _manifest_cache[key]
        return None
    return data


def _set_cached(key: str, data: dict, ttl: float = _CACHE_TTL_SECONDS) -> None:
    _manifest_cache[key] = (data, time.time(), ttl)


def _empty_manifest() -> dict:
    return {
        "entities": {},
        "total": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _fetch_manifest_from_db() -> dict:
    from supabase_client import get_supabase

    sb = get_supabase()

    rows = await asyncio.to_thread(
        lambda: sb.table("seo_coverage_manifest")
        .select("entity_type, entity_id, coverage_status, last_activity_at, updated_at")
        .order("entity_type")
        .execute()
    )

    entities: dict[str, dict] = {}
    for row in (rows.data or []):
        etype = row["entity_type"]
        eid = row["entity_id"]
        if etype not in entities:
            entities[etype] = {}
        entities[etype][eid] = {
            "coverage_status": row["coverage_status"],
            "last_activity_at": row.get("last_activity_at"),
            "updated_at": row["updated_at"],
        }

    total = sum(len(v) for v in entities.values())
    return {
        "entities": entities,
        "total": total,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


_MANIFEST_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=3600, stale-while-revalidate=7200, stale-if-error=86400",
    "Vary": "Accept-Encoding",
}


@router.get(
    "/seo/coverage-manifest",
    response_model=CoverageManifestResponse,
    summary="Manifest de cobertura de dados por entidade (para sitemap gate)",
)
async def seo_coverage_manifest() -> JSONResponse:
    """Retorna status de cobertura de dados para cada entidade do catálogo.

    Usado pelo frontend para filtrar URLs do sitemap.xml:
    - full / partial → incluir no sitemap
    - historical_empty → incluir com priority 0.3
    - empty → excluir do sitemap
    """
    cached = _get_cached("manifest")
    if cached:
        return JSONResponse(content=cached, headers=_MANIFEST_CACHE_HEADERS)

    try:
        data = await asyncio.wait_for(_fetch_manifest_from_db(), timeout=_BUDGET_S)
        _set_cached("manifest", data)
        return JSONResponse(content=data, headers=_MANIFEST_CACHE_HEADERS)
    except Exception as exc:
        logger.error("seo_coverage_manifest fetch failed: %s", exc)
        sentry_sdk.capture_exception(exc)
        empty = _empty_manifest()
        _set_cached("manifest", empty, _NEGATIVE_CACHE_TTL_SECONDS)
        return JSONResponse(content=empty, headers=_MANIFEST_CACHE_HEADERS)
