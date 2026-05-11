"""SEO-COVERAGE-MANIFEST-001 (#1039): Coverage manifest endpoint.

GET /v1/seo/coverage-manifest — Returns per-slug coverage status from
seo_coverage_manifest table. Used by the frontend sitemap gate to exclude
URLs with no real data (coverage_status='empty') while keeping
historical_empty slugs with reduced priority.

Public (no auth). Cache: InMemory 1h TTL on success, 5min negative TTL on error.
Budget: 5s < Supabase service_role statement_timeout=15s.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Response
from pydantic import BaseModel

from pipeline.budget import _run_with_budget

logger = logging.getLogger(__name__)
router = APIRouter(tags=["seo-coverage"])

_CACHE_TTL_SECONDS = 60 * 60          # 1h success
_NEGATIVE_CACHE_TTL_SECONDS = 5 * 60  # 5min on error/timeout
_BUDGET_S = 5.0

# Simple in-memory cache: {"data": <dict|None>, "expires": <float>}
_coverage_cache: dict = {"data": None, "expires": 0.0}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CoverageEntry(BaseModel):
    coverage_status: Literal["full", "partial", "empty", "historical_empty"]
    bid_count: int
    last_updated: str  # ISO-8601 string (avoids datetime serialisation edge-cases)


class CoverageManifestResponse(BaseModel):
    manifest: dict[str, CoverageEntry]
    generated_at: str
    total_entities: int


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.get(
    "/seo/coverage-manifest",
    response_model=CoverageManifestResponse,
    summary="Per-slug coverage status for sitemap gate (SEO-COVERAGE-MANIFEST-001)",
)
async def get_coverage_manifest(response: Response):
    """Return the latest seo_coverage_manifest rows as a keyed dict.

    AC1: <2s response time (served from 1h in-memory cache after first build).
    AC7: historical_empty slugs are included — sitemap gate uses priority=0.3,
         not excluded, so /observatorio/raio-x-marco-2026 stays accessible.
    """
    # Cache headers — allow CDN/ISR to cache for 1h (align with Next.js revalidate=3600)
    response.headers["Cache-Control"] = "public, max-age=3600, stale-while-revalidate=300"

    now = time.time()
    cached = _coverage_cache.get("data")
    if cached is not None and now < _coverage_cache.get("expires", 0.0):
        return cached

    try:
        data = await _run_with_budget(
            asyncio.to_thread(_fetch_manifest),
            budget=_BUDGET_S,
            phase="route",
            source="seo_coverage_manifest.get_coverage_manifest",
        )
        _coverage_cache["data"] = data
        _coverage_cache["expires"] = now + _CACHE_TTL_SECONDS
        return data
    except asyncio.TimeoutError:
        logger.warning(
            "get_coverage_manifest: budget %.0fs exceeded — returning empty negative cache",
            _BUDGET_S,
        )
        try:
            import sentry_sdk
            sentry_sdk.capture_message(
                "coverage_manifest_timeout",
                level="warning",
                tags={"endpoint": "seo/coverage-manifest", "outcome": "timeout"},
            )
        except Exception:
            pass
        empty = _empty_manifest_response()
        _coverage_cache["data"] = empty
        _coverage_cache["expires"] = now + _NEGATIVE_CACHE_TTL_SECONDS
        return empty
    except Exception as exc:
        logger.error("get_coverage_manifest unexpected error: %s", exc)
        empty = _empty_manifest_response()
        _coverage_cache["data"] = empty
        _coverage_cache["expires"] = now + _NEGATIVE_CACHE_TTL_SECONDS
        return empty


def _empty_manifest_response() -> CoverageManifestResponse:
    return CoverageManifestResponse(
        manifest={},
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_entities=0,
    )


def _fetch_manifest() -> CoverageManifestResponse:
    """Sync query — supabase-py is sync; caller wraps in asyncio.to_thread."""
    try:
        from supabase_client import get_supabase

        sb = get_supabase()

        page_size = 1000
        offset = 0
        all_rows: list[dict] = []

        while True:
            resp = (
                sb.table("seo_coverage_manifest")
                .select("entity_type,slug,coverage_status,bid_count,last_updated")
                .range(offset, offset + page_size - 1)
                .execute()
            )
            if not resp.data:
                break
            all_rows.extend(resp.data)
            if len(resp.data) < page_size:
                break
            offset += page_size

        manifest: dict[str, CoverageEntry] = {}
        for row in all_rows:
            slug = (row.get("slug") or "").strip()
            status = row.get("coverage_status") or "empty"
            if not slug:
                continue
            # Key: "<entity_type>/<slug>" for namespacing (e.g. "cnpj/12345678000199")
            key = f"{row.get('entity_type', 'unknown')}/{slug}"
            manifest[key] = CoverageEntry(
                coverage_status=status,  # type: ignore[arg-type]
                bid_count=int(row.get("bid_count") or 0),
                last_updated=str(row.get("last_updated") or datetime.now(timezone.utc).isoformat()),
            )

        logger.info(
            "coverage_manifest: %d entries loaded from seo_coverage_manifest",
            len(manifest),
        )

        return CoverageManifestResponse(
            manifest=manifest,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_entities=len(manifest),
        )

    except Exception as exc:
        logger.error("_fetch_manifest query failed: %s", exc)
        return _empty_manifest_response()
