"""Weekly digest endpoint for /blog/weekly/[slug].

Generates automated weekly summaries of bidding activity from the PNCP datalake.

Public (no auth). Cache: InMemory 6h TTL.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sectors import SECTORS
from unified_schemas.unified import VALID_UFS
from utils.seo_semaphore import seo_semaphore, SEO_SEMAPHORE_DISABLED

logger = logging.getLogger(__name__)
router = APIRouter(tags=["weekly_digest"])

# POOL-001 (#2047): SEOSemaphore (Priority 3, max 2 concurrent).
_SEM = seo_semaphore("weekly_digest", max_concurrent=2)

_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6h
_digest_cache: dict[str, tuple[dict, float]] = {}

ALL_UFS = sorted(VALID_UFS)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class WeeklyHighlight(BaseModel):
    sector_name: str
    sector_id: str
    count: int
    avg_value: float
    trend: str  # "up", "down", "stable"


class WeeklyUfStat(BaseModel):
    uf: str
    count: int
    total_value: float


class WeeklyModalidadeStat(BaseModel):
    modalidade: str
    count: int
    pct: float


class WeeklyDigestResponse(BaseModel):
    year: int
    week: int
    slug: str
    title: str
    period_start: str
    period_end: str
    total_bids: int
    total_value: float
    avg_value: float
    by_sector: list[WeeklyHighlight]
    by_uf: list[WeeklyUfStat]
    by_modalidade: list[WeeklyModalidadeStat]
    top_sector: str
    top_uf: str
    updated_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/blog/weekly/latest",
    response_model=WeeklyDigestResponse,
    summary="Digest semanal atual (público)",
)
async def weekly_digest_latest():
    now = datetime.now(timezone.utc)
    iso_cal = now.isocalendar()
    year, week = iso_cal[0], iso_cal[1]

    cache_key = f"{year}:{week}"
    cached = _get_cached(cache_key)
    if cached:
        return WeeklyDigestResponse(**cached)

    data = await _generate_weekly_data(year, week)
    _set_cached(cache_key, data)
    return WeeklyDigestResponse(**data)


@router.get(
    "/blog/weekly/{year}/{week}",
    response_model=WeeklyDigestResponse,
    summary="Digest semanal para um período específico (público)",
)
async def weekly_digest_by_week(year: int, week: int):
    if year < 2020 or year > 2100:
        raise HTTPException(status_code=400, detail="Ano inválido")
    if week < 1 or week > 53:
        raise HTTPException(status_code=400, detail="Semana inválida (1-53)")

    cache_key = f"{year}:{week}"
    cached = _get_cached(cache_key)
    if cached:
        return WeeklyDigestResponse(**cached)

    data = await _generate_weekly_data(year, week)
    _set_cached(cache_key, data)
    return WeeklyDigestResponse(**data)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cached(key: str) -> Optional[dict]:
    if key not in _digest_cache:
        return None
    data, ts = _digest_cache[key]
    if time.time() - ts >= _CACHE_TTL_SECONDS:
        del _digest_cache[key]
        return None
    return data


def _set_cached(key: str, data: dict) -> None:
    _digest_cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

def _week_date_range(year: int, week: int) -> tuple[datetime, datetime]:
    """Return (period_start, period_end) for the ISO week."""
    jan4 = datetime(year, 1, 4)
    start_of_week1 = jan4 - timedelta(days=jan4.weekday())
    period_start = start_of_week1 + timedelta(weeks=week - 1)
    period_end = period_start + timedelta(days=6)
    return period_start, period_end


_MODALIDADE_NAMES: dict[int, str] = {
    4: "Concorrência",
    5: "Pregão Eletrônico",
    6: "Pregão Presencial",
    7: "Leilão",
    8: "Inexigibilidade",
    12: "Dispensa",
}


async def _generate_weekly_data(year: int, week: int) -> dict:
    period_start, period_end = _week_date_range(year, week)

    results: list[dict] = []
    try:
        from datalake_query import query_datalake

        results = await query_datalake(
            ufs=ALL_UFS,
            data_inicial=period_start.strftime("%Y-%m-%d"),
            data_final=period_end.strftime("%Y-%m-%d"),
            limit=5000,
        )
    except Exception as e:
        logger.warning("WeeklyDigest: datalake query failed for %s-W%s: %s", year, week, e)

    total_bids = len(results)

    # Aggregate values
    all_values = []
    for r in results:
        v = r.get("valorTotalEstimado") or r.get("valorEstimado") or r.get("valor_estimado")
        if v and isinstance(v, (int, float)) and v > 0:
            all_values.append(float(v))

    total_value = sum(all_values)
    avg_value = total_value / len(all_values) if all_values else 0.0

    # --- By sector ---
    sector_counts: dict[str, int] = {}
    sector_values: dict[str, list[float]] = {}

    for r in results:
        objeto = r.get("objeto") or r.get("descricao") or ""
        objeto_lower = objeto.lower()
        matched_sid = None
        for sid, sector in SECTORS.items():
            if any(kw.lower() in objeto_lower for kw in sector.keywords):
                matched_sid = sid
                break
        if matched_sid is None:
            continue
        sector_counts[matched_sid] = sector_counts.get(matched_sid, 0) + 1
        v = r.get("valorTotalEstimado") or r.get("valorEstimado") or r.get("valor_estimado")
        if v and isinstance(v, (int, float)) and v > 0:
            sector_values.setdefault(matched_sid, []).append(float(v))

    by_sector_sorted = sorted(sector_counts.items(), key=lambda x: x[1], reverse=True)
    by_sector = []
    for sid, count in by_sector_sorted[:10]:
        vals = sector_values.get(sid, [])
        avg_v = sum(vals) / len(vals) if vals else 0.0
        by_sector.append(
            WeeklyHighlight(
                sector_name=SECTORS[sid].name if sid in SECTORS else sid,
                sector_id=sid,
                count=count,
                avg_value=round(avg_v, 2),
                trend="stable",  # no prior week data in this request
            )
        )

    top_sector = by_sector[0].sector_name if by_sector else "N/D"

    # --- By UF ---
    uf_counts: dict[str, int] = {}
    uf_values: dict[str, float] = {}

    for r in results:
        uf = r.get("uf") or r.get("unidadeFederativa") or ""
        if not uf or uf not in VALID_UFS:
            continue
        uf_counts[uf] = uf_counts.get(uf, 0) + 1
        v = r.get("valorTotalEstimado") or r.get("valorEstimado") or r.get("valor_estimado")
        if v and isinstance(v, (int, float)) and v > 0:
            uf_values[uf] = uf_values.get(uf, 0.0) + float(v)

    by_uf_sorted = sorted(uf_counts.items(), key=lambda x: x[1], reverse=True)
    by_uf = [
        WeeklyUfStat(uf=uf, count=cnt, total_value=round(uf_values.get(uf, 0.0), 2))
        for uf, cnt in by_uf_sorted[:15]
    ]

    top_uf = by_uf[0].uf if by_uf else "N/D"

    # --- By modalidade ---
    mod_counts: dict[str, int] = {}
    for r in results:
        mod_code = r.get("modalidade") or r.get("codigoModalidadeContratacao")
        if mod_code is not None:
            try:
                mod_int = int(mod_code)
                mod_name = _MODALIDADE_NAMES.get(mod_int, f"Modalidade {mod_int}")
            except (ValueError, TypeError):
                mod_name = str(mod_code)
        else:
            mod_name = "Outros"
        mod_counts[mod_name] = mod_counts.get(mod_name, 0) + 1

    by_modalidade = []
    for mod_name, cnt in sorted(mod_counts.items(), key=lambda x: x[1], reverse=True):
        pct = round((cnt / total_bids * 100), 1) if total_bids > 0 else 0.0
        by_modalidade.append(WeeklyModalidadeStat(modalidade=mod_name, count=cnt, pct=pct))

    # Build slug and title
    slug = f"{year}-w{week:02d}"
    title = f"Semana {week}: {total_bids} editais publicados"
    if top_sector != "N/D":
        title += f", setor {top_sector} em destaque"

    return {
        "year": year,
        "week": week,
        "slug": slug,
        "title": title,
        "period_start": period_start.strftime("%Y-%m-%d"),
        "period_end": period_end.strftime("%Y-%m-%d"),
        "total_bids": total_bids,
        "total_value": round(total_value, 2),
        "avg_value": round(avg_value, 2),
        "by_sector": [s.model_dump() for s in by_sector],
        "by_uf": [u.model_dump() for u in by_uf],
        "by_modalidade": [m.model_dump() for m in by_modalidade],
        "top_sector": top_sector,
        "top_uf": top_uf,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
