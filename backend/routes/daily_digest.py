"""Daily digest endpoint for /blog/licitacoes-do-dia.

Generates automated daily summaries of bidding activity from the PNCP datalake.

Public (no auth). Cache: InMemory 1h TTL.

Endpoints:
  GET /blog/daily/latest      — today's digest
  GET /blog/daily/{date}      — digest for a specific date (YYYY-MM-DD)
"""

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from sectors import SECTORS
from unified_schemas.unified import VALID_UFS
from utils.seo_semaphore import seo_semaphore, SEO_SEMAPHORE_DISABLED

logger = logging.getLogger(__name__)
router = APIRouter(tags=["daily_digest"])

# POOL-001 (#2047): SEOSemaphore (Priority 3, max 2 concurrent).
_SEM = seo_semaphore("daily_digest", max_concurrent=2)

_CACHE_TTL_SECONDS = 3600  # 1h
_daily_cache: dict[str, tuple[dict, float]] = {}

ALL_UFS = sorted(VALID_UFS)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_MODALIDADE_NAMES: dict[int, str] = {
    4: "Concorrência",
    5: "Pregão Eletrônico",
    6: "Pregão Presencial",
    7: "Leilão",
    8: "Inexigibilidade",
    12: "Dispensa",
}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class DailySector(BaseModel):
    sector_name: str
    sector_id: str
    count: int
    avg_value: float


class DailyUf(BaseModel):
    uf: str
    count: int
    total_value: float


class DailyModalidade(BaseModel):
    modalidade: str
    count: int
    pct: float


class DailyHighlight(BaseModel):
    titulo: str
    orgao: str
    valor: Optional[float] = None
    uf: str
    setor: str


class DailyDigestResponse(BaseModel):
    date: str
    title: str
    total_bids: int
    total_value: float
    avg_value: float
    by_sector: list[DailySector]
    by_uf: list[DailyUf]
    by_modalidade: list[DailyModalidade]
    highlights: list[DailyHighlight]
    top_sector: str
    top_uf: str
    updated_at: str


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cached(key: str) -> Optional[dict]:
    if key not in _daily_cache:
        return None
    data, ts = _daily_cache[key]
    if time.time() - ts >= _CACHE_TTL_SECONDS:
        del _daily_cache[key]
        return None
    return data


def _set_cached(key: str, data: dict) -> None:
    _daily_cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/blog/daily/latest",
    response_model=DailyDigestResponse,
    summary="Digest diario atual (publico)",
)
async def daily_digest_latest():
    # Use Sao Paulo timezone for "today"
    now_sp = datetime.now(timezone(timedelta(hours=-3)))
    date_str = now_sp.strftime("%Y-%m-%d")

    cached = _get_cached(date_str)
    if cached:
        return DailyDigestResponse(**cached)

    data = await _generate_daily_data(date_str)
    _set_cached(date_str, data)
    return DailyDigestResponse(**data)


@router.get(
    "/blog/daily/{date}",
    response_model=DailyDigestResponse,
    summary="Digest diario para uma data especifica (publico)",
)
async def daily_digest_by_date(date: str):
    if not _DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="Formato invalido (esperado YYYY-MM-DD)")

    try:
        parsed = datetime.strptime(date, "%Y-%m-%d")
        if parsed.year < 2020 or parsed.year > 2100:
            raise ValueError("Year out of range")
    except ValueError:
        raise HTTPException(status_code=400, detail="Data invalida")

    cached = _get_cached(date)
    if cached:
        return DailyDigestResponse(**cached)

    data = await _generate_daily_data(date)
    _set_cached(date, data)
    return DailyDigestResponse(**data)


# ---------------------------------------------------------------------------
# Data generation
# ---------------------------------------------------------------------------

async def _generate_daily_data(date_str: str) -> dict:
    results: list[dict] = []
    try:
        from datalake_query import query_datalake

        results = await query_datalake(
            ufs=ALL_UFS,
            data_inicial=date_str,
            data_final=date_str,
            limit=5000,
        )
    except Exception as e:
        logger.warning("DailyDigest: datalake query failed for %s: %s", date_str, e)

    total_bids = len(results)

    # Aggregate values
    all_values: list[float] = []
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
        objeto = r.get("objeto") or r.get("descricao") or r.get("objetoCompra") or ""
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
        by_sector.append({
            "sector_name": SECTORS[sid].name if sid in SECTORS else sid,
            "sector_id": sid,
            "count": count,
            "avg_value": round(avg_v, 2),
        })

    top_sector = by_sector[0]["sector_name"] if by_sector else "N/D"

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
        {"uf": uf, "count": cnt, "total_value": round(uf_values.get(uf, 0.0), 2)}
        for uf, cnt in by_uf_sorted[:15]
    ]

    top_uf = by_uf[0]["uf"] if by_uf else "N/D"

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
        by_modalidade.append({"modalidade": mod_name, "count": cnt, "pct": pct})

    # --- Highlights (top 5 by value) ---
    highlights = []
    valued_results = []
    for r in results:
        v = r.get("valorTotalEstimado") or r.get("valorEstimado") or r.get("valor_estimado")
        if v and isinstance(v, (int, float)) and v > 0:
            valued_results.append((float(v), r))

    valued_results.sort(key=lambda x: x[0], reverse=True)
    for valor, r in valued_results[:5]:
        titulo = r.get("objetoCompra") or r.get("objeto") or r.get("title") or "Sem titulo"
        if len(titulo) > 120:
            titulo = titulo[:117] + "..."

        org = r.get("orgaoEntidade", {})
        orgao = (org.get("razaoSocial") if isinstance(org, dict) else None) or r.get("orgao") or "N/D"

        uf = r.get("uf") or r.get("unidadeFederativa") or ""

        # Match sector
        objeto_lower = (r.get("objeto") or r.get("objetoCompra") or "").lower()
        setor = "Outros"
        for sid, sector in SECTORS.items():
            if any(kw.lower() in objeto_lower for kw in sector.keywords):
                setor = sector.name
                break

        highlights.append({
            "titulo": titulo,
            "orgao": orgao,
            "valor": valor,
            "uf": uf,
            "setor": setor,
        })

    # Build title
    title = f"{date_str}: {total_bids} editais publicados"
    if top_sector != "N/D":
        title += f", destaque {top_sector}"

    return {
        "date": date_str,
        "title": title,
        "total_bids": total_bids,
        "total_value": round(total_value, 2),
        "avg_value": round(avg_value, 2),
        "by_sector": by_sector,
        "by_uf": by_uf,
        "by_modalidade": by_modalidade,
        "highlights": highlights,
        "top_sector": top_sector,
        "top_uf": top_uf,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
