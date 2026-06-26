"""P2 SEO: Public aggregated PNCP datalake data endpoint for /dados hub.

Returns aggregated stats (by sector, UF, modalidade, 30-day trend) from
the local pncp_raw_bids datalake, enabling an interactive public data panel.

Public (no auth). Cache: InMemory 6h TTL.
"""

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.seo_semaphore import seo_semaphore, SEO_SEMAPHORE_DISABLED

logger = logging.getLogger(__name__)
router = APIRouter(tags=["dados_publicos"])

# POOL-001 (#2047): SEOSemaphore (Priority 3, max 2 concurrent).
_SEM = seo_semaphore("dados_publicos", max_concurrent=2)

_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6h
_dados_cache: dict[str, tuple[dict, float]] = {}

_MODALIDADE_NAMES: dict[int, str] = {
    4: "Concorrência",
    5: "Pregão Eletrônico",
    6: "Pregão Presencial",
    7: "Leilão",
    8: "Dispensa",
    12: "Credenciamento",
}


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class SectorAggregate(BaseModel):
    sector_id: str
    sector_name: str
    count: int
    total_value: float
    avg_value: float


class UfAggregate(BaseModel):
    uf: str
    count: int
    total_value: float


class ModalidadeAggregate(BaseModel):
    code: int
    name: str
    count: int
    pct: float


class TrendPoint(BaseModel):
    date: str  # "2026-04-01"
    count: int
    value: float


class DadosAgregadosResponse(BaseModel):
    updated_at: str
    period: str  # "Últimos 30 dias"
    period_start: str
    period_end: str
    total_bids: int
    total_value: float
    avg_value: float
    by_sector: list[SectorAggregate]
    by_uf: list[UfAggregate]
    by_modalidade: list[ModalidadeAggregate]
    trend_30d: list[TrendPoint]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/dados/agregados",
    response_model=DadosAgregadosResponse,
    summary="Dados agregados do PNCP para o painel público (sem autenticação)",
)
async def dados_agregados():
    cached = _get_cached("global")
    if cached:
        return DadosAgregadosResponse(**cached)

    data = await _generate_dados()
    _set_cached("global", data)
    return DadosAgregadosResponse(**data)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _get_cached(key: str) -> Optional[dict]:
    if key not in _dados_cache:
        return None
    data, ts = _dados_cache[key]
    if time.time() - ts >= _CACHE_TTL_SECONDS:
        del _dados_cache[key]
        return None
    return data


def _set_cached(key: str, data: dict) -> None:
    _dados_cache[key] = (data, time.time())


# ---------------------------------------------------------------------------
# Data generation (datalake query)
# ---------------------------------------------------------------------------


def _extract_value(record: dict) -> float:
    """Extract numeric bid value from a datalake record (fail-safe)."""
    for field in ("valorTotalEstimado", "valorEstimado", "valor_estimado"):
        v = record.get(field)
        if v and isinstance(v, (int, float)) and v > 0:
            return float(v)
    return 0.0


def _extract_date(record: dict) -> Optional[str]:
    """Extract publication date string 'YYYY-MM-DD' from a datalake record."""
    for field in ("dataPublicacaoPncp", "data_publicacao"):
        v = record.get(field)
        if v and isinstance(v, str) and len(v) >= 10:
            return v[:10]
    return None


async def _generate_dados() -> dict:
    from datalake_query import query_datalake
    from sectors import SECTORS
    from unified_schemas.unified import VALID_UFS

    now = datetime.now(timezone.utc)
    data_final = now.strftime("%Y-%m-%d")
    data_inicial = (now - timedelta(days=30)).strftime("%Y-%m-%d")

    all_results: list[dict] = []
    try:
        all_results = await query_datalake(
            ufs=list(VALID_UFS),
            data_inicial=data_inicial,
            data_final=data_final,
            limit=5000,
        )
    except Exception as e:
        logger.warning("DadosPublicos: datalake query failed: %s", e)

    total_bids = len(all_results)
    total_value = 0.0

    # --- by_uf ---
    uf_counts: dict[str, int] = defaultdict(int)
    uf_values: dict[str, float] = defaultdict(float)

    # --- by_modalidade ---
    mod_counts: dict[int, int] = defaultdict(int)

    # --- trend ---
    trend_counts: dict[str, int] = defaultdict(int)
    trend_values: dict[str, float] = defaultdict(float)

    # --- by_sector (keyword match on objeto field) ---
    sector_counts: dict[str, int] = defaultdict(int)
    sector_values: dict[str, float] = defaultdict(float)

    for record in all_results:
        value = _extract_value(record)
        total_value += value

        # UF
        uf = (record.get("uf") or record.get("unidade_federativa") or "").upper()
        if uf:
            uf_counts[uf] += 1
            uf_values[uf] += value

        # Modalidade
        mod_code = record.get("codigoModalidadeContratacao") or record.get("modalidade_code")
        if mod_code:
            try:
                mod_counts[int(mod_code)] += 1
            except (ValueError, TypeError):
                pass

        # Trend
        date_str = _extract_date(record)
        if date_str:
            trend_counts[date_str] += 1
            trend_values[date_str] += value

        # Sector — match any keyword against objeto
        objeto = (record.get("objeto") or record.get("objetoCompra") or "").lower()
        matched = False
        for sid, sector in SECTORS.items():
            if matched:
                break
            if not hasattr(sector, "keywords"):
                continue
            for kw in sector.keywords:
                if kw.lower() in objeto:
                    sector_counts[sid] += 1
                    sector_values[sid] += value
                    matched = True
                    break

    avg_value = total_value / total_bids if total_bids else 0.0

    # Build by_sector list — sorted by count desc
    by_sector = [
        SectorAggregate(
            sector_id=sid,
            sector_name=SECTORS[sid].name if hasattr(SECTORS[sid], "name") else sid,
            count=sector_counts[sid],
            total_value=round(sector_values[sid], 2),
            avg_value=round(sector_values[sid] / sector_counts[sid], 2)
            if sector_counts[sid]
            else 0.0,
        )
        for sid in SECTORS
        if sector_counts[sid] > 0
    ]
    by_sector.sort(key=lambda x: x.count, reverse=True)

    # Build by_uf list — sorted by count desc
    by_uf = [
        UfAggregate(
            uf=uf,
            count=uf_counts[uf],
            total_value=round(uf_values[uf], 2),
        )
        for uf in uf_counts
    ]
    by_uf.sort(key=lambda x: x.count, reverse=True)

    # Build by_modalidade list — sorted by count desc
    total_mod = sum(mod_counts.values()) or 1
    by_modalidade = [
        ModalidadeAggregate(
            code=code,
            name=_MODALIDADE_NAMES.get(code, f"Modalidade {code}"),
            count=count,
            pct=round(count / total_mod * 100, 1),
        )
        for code, count in sorted(mod_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # Build trend_30d — sorted by date asc
    trend_30d = [
        TrendPoint(
            date=date_str,
            count=trend_counts[date_str],
            value=round(trend_values[date_str], 2),
        )
        for date_str in sorted(trend_counts.keys())
    ]

    return {
        "updated_at": now.isoformat(),
        "period": "Últimos 30 dias",
        "period_start": data_inicial,
        "period_end": data_final,
        "total_bids": total_bids,
        "total_value": round(total_value, 2),
        "avg_value": round(avg_value, 2),
        "by_sector": [s.model_dump() for s in by_sector],
        "by_uf": [u.model_dump() for u in by_uf],
        "by_modalidade": [m.model_dump() for m in by_modalidade],
        "trend_30d": [t.model_dump() for t in trend_30d],
    }
