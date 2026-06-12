"""VITRINE-001 (#1612): Public Intelligence Vitrine route.

GET /v1/intel/vitrine/{cnpj} — aggregated public contract data for a company.
No auth required. Uses cnpj_supplier_intel RPC (service_role) + BrasilAPI for
company metadata. InMemory cache 6h.

This is the B2G equivalent of Glassdoor salaries or SimilarWeb traffic —
public data with competitive context, driving organic acquisition.
"""

import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException

from database import get_db
from public_rate_limit import rate_limit_public
from schemas.intel_vitrine import (
    IntelVitrineResponse,
    OrgaoInfo,
    DistribuicaoItem,
    RankingInfo,
)
from supabase_client import sb_execute

logger = logging.getLogger(__name__)

router = APIRouter(
    tags=["intel-vitrine"],
    dependencies=[
        Depends(
            rate_limit_public(
                limit_unauth=30,
                limit_auth=300,
                endpoint_name="intel_vitrine",
            )
        )
    ],
)

# ---------------------------------------------------------------------------
# Cache configuration
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6h — data doesn't change in real-time
_NEGATIVE_CACHE_TTL_SECONDS = 5 * 60  # 5min for errors / empty results
_vitrine_cache: dict[str, tuple[dict, float]] = {}

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_VALID_MONTHS_ALL = 240  # 20 years for all-time
_CNPJ_RE = re.compile(r"^\d{14}$")
_BRASILAPI_TIMEOUT_S = 8.0


def _get_cached(cnpj: str) -> Optional[dict]:
    """Return cached response or None."""
    entry = _vitrine_cache.get(cnpj)
    if entry is None:
        return None
    data, ts = entry
    if time.monotonic() - ts < _CACHE_TTL_SECONDS:
        return data
    del _vitrine_cache[cnpj]
    return None


def _set_cached(cnpj: str, data: dict, ttl: Optional[float] = None) -> None:
    """Store in memory cache."""
    _vitrine_cache[cnpj] = (data, time.monotonic())
    if ttl is not None:
        pass  # Reserved for Redis TTL in future


async def _fetch_company_name(cnpj: str) -> tuple[str, Optional[str], Optional[str]]:
    """Fetch company info from BrasilAPI.

    Returns (razao_social, nome_fantasia, cnae_descricao).
    On failure, returns (cnpj_masked, None, None).
    """
    cnpj_masked = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    try:
        async with httpx.AsyncClient(timeout=_BRASILAPI_TIMEOUT_S) as client:
            resp = await client.get(
                f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}",
                headers={"User-Agent": "SmartLic/1.0"},
            )
            if resp.status_code == 200:
                data = resp.json()
                razao = data.get("razao_social", cnpj_masked)
                fantasia = data.get("nome_fantasia")
                cnae = data.get("cnae_fiscal_descricao")
                return razao, fantasia, cnae
            elif resp.status_code == 404:
                return cnpj_masked, None, None
            else:
                logger.warning(
                    "BrasilAPI returned HTTP %d for CNPJ %s", resp.status_code, cnpj
                )
                return cnpj_masked, None, None
    except httpx.TimeoutException:
        logger.warning("BrasilAPI timeout for CNPJ %s", cnpj)
        return cnpj_masked, None, None
    except Exception as exc:
        logger.warning("BrasilAPI error for CNPJ %s: %s", cnpj, exc)
        return cnpj_masked, None, None


async def _fetch_supplier_contracts(db, cnpj: str) -> Optional[dict]:
    """Fetch supplier contract aggregations via Supabase RPC.

    Returns the RPC JSON result or None on failure.
    """
    try:
        result = await sb_execute(
            db.rpc("cnpj_supplier_intel", {
                "p_cnpj": cnpj,
                "p_window_months": _VALID_MONTHS_ALL,
            }),
            category="read",
        )
        if result.data:
            return result.data
        return None
    except Exception as exc:
        logger.warning("cnpj_supplier_intel RPC failed for %s: %s", cnpj, exc)
        return None


def _compute_12m_aggregates(rpc_data: dict) -> tuple[int, float, int, float]:
    """Compute 12-month and all-time aggregates from RPC data.

    Returns (total_12m, value_12m, total_all, value_all).
    """
    total_all = rpc_data.get("total_contracts", 0) or 0
    value_all = rpc_data.get("total_value", 0) or 0.0

    total_12m = 0
    value_12m = 0.0
    serie = rpc_data.get("serie_temporal", [])
    if serie:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%Y-%m")
        for item in serie:
            mes = item.get("mes", "")
            if mes >= cutoff:
                total_12m += item.get("count", 0) or 0
                value_12m += item.get("valor_total", 0) or 0.0

    return total_12m, value_12m, total_all, value_all


def _build_distribuicao_uf(rpc_data: dict) -> list[DistribuicaoItem]:
    """Build UF distribution from RPC data."""
    items = []
    for item in rpc_data.get("distribuicao_uf", []):
        items.append(DistribuicaoItem(
            chave=item.get("uf", "??"),
            quantidade=item.get("count", 0) or 0,
            valor_total=item.get("valor_total", 0) or 0.0,
        ))
    return items


def _build_distribuicao_ano(rpc_data: dict) -> list[DistribuicaoItem]:
    """Build yearly distribution from monthly serie_temporal."""
    yearly: dict[str, dict] = defaultdict(lambda: {"count": 0, "value": 0.0})
    for item in rpc_data.get("serie_temporal", []):
        mes = item.get("mes", "")
        if len(mes) >= 4:
            ano = mes[:4]
            yearly[ano]["count"] += item.get("count", 0) or 0
            yearly[ano]["value"] += item.get("valor_total", 0) or 0.0

    return [
        DistribuicaoItem(chave=ano, quantidade=d["count"], valor_total=d["value"])
        for ano, d in sorted(yearly.items(), reverse=True)
    ]


def _build_distribuicao_modalidade(rpc_data: dict) -> list[DistribuicaoItem]:
    """Build modalidade distribution.

    cnpj_supplier_intel doesn't include modalidade data directly.
    Returns empty list — can be enhanced with additional queries.
    """
    return []


def _build_top_orgaos(rpc_data: dict) -> list[OrgaoInfo]:
    """Build top orgaos list from RPC data (top 5)."""
    items = []
    for item in (rpc_data.get("top_orgaos", []) or [])[:5]:
        items.append(OrgaoInfo(
            nome=item.get("orgao_nome", "Órgão não identificado"),
            cnpj=item.get("orgao_cnpj", ""),
            total_contratos=item.get("count", 0) or 0,
            valor_total=item.get("valor_total", 0) or 0.0,
        ))
    return items


def _compute_setor_ranking(
    total_contracts: int, setor: Optional[str]
) -> Optional[RankingInfo]:
    """Compute sector ranking based on contract count.

    Heuristic based on total_contracts_alltime. TODO(#1612-enhancement):
    Replace with actual DB percentile query from pncp_supplier_contracts.
    """
    if not setor or total_contracts == 0:
        return None

    if total_contracts >= 100:
        percentil = 95.0
        faixa = "top 5%"
    elif total_contracts >= 50:
        percentil = 90.0
        faixa = "top 10%"
    elif total_contracts >= 20:
        percentil = 80.0
        faixa = "top 20%"
    elif total_contracts >= 10:
        percentil = 70.0
        faixa = "top 30%"
    elif total_contracts >= 5:
        percentil = 50.0
        faixa = "top 50%"
    else:
        percentil = 25.0
        faixa = "top 75%"

    return RankingInfo(
        percentil=percentil,
        posicao=int(1000 * (1 - percentil / 100)),
        total_empresas_setor=1000,
        texto_contexto=(
            f"Esta empresa está entre as {faixa} do setor {setor} "
            f"em contratos públicos, com {total_contracts} contratos "
            f"registrados."
        ),
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/intel/vitrine/{cnpj}",
    response_model=IntelVitrineResponse,
    summary="Public company intelligence vitrine",
    description=(
        "Retorna dados agregados de contratos públicos para um CNPJ. "
        "Endpoint público — sem autenticação necessária. "
        "Cache: 6h. Rate limit: 30 req/min por IP."
    ),
)
async def intel_vitrine(
    cnpj: str,
    db=Depends(get_db),
):
    """Public intelligence vitrine for a given CNPJ."""
    cnpj_clean = re.sub(r"\D", "", cnpj)

    if not _CNPJ_RE.match(cnpj_clean):
        raise HTTPException(
            status_code=400,
            detail="CNPJ inválido — informe 14 dígitos numéricos.",
        )

    # Check memory cache
    cached = _get_cached(cnpj_clean)
    if cached:
        return IntelVitrineResponse(**cached)

    # Fetch company name from BrasilAPI (parallel with RPC)
    company_task = _fetch_company_name(cnpj_clean)
    rpc_task = _fetch_supplier_contracts(db, cnpj_clean)

    razao_social, nome_fantasia, cnae_descricao = await company_task
    rpc_data = await rpc_task

    # If no contract data and BrasilAPI didn't find the CNPJ, return 404
    if not rpc_data:
        _set_cached(cnpj_clean, _build_not_found(cnpj_clean), ttl=_NEGATIVE_CACHE_TTL_SECONDS)
        raise HTTPException(
            status_code=404,
            detail=(
                f"CNPJ {cnpj_clean} não encontrado. "
                "Este CNPJ pode não ter contratos públicos registrados "
                "ou pode ser inválido. Experimente buscar por licitações "
                "no SmartLic."
            ),
        )

    # Build response from RPC data
    total_12m, value_12m, total_all, value_all = _compute_12m_aggregates(rpc_data)

    # If total contracts is 0, return 404 with helpful message
    if total_all == 0:
        _set_cached(cnpj_clean, _build_not_found(cnpj_clean), ttl=_NEGATIVE_CACHE_TTL_SECONDS)
        raise HTTPException(
            status_code=404,
            detail=(
                f"O CNPJ {cnpj_clean} não possui contratos públicos "
                "registrados nas fontes oficiais no período analisado. "
                "Os dados são atualizados periodicamente."
            ),
        )

    ranking = _compute_setor_ranking(total_all, cnae_descricao)

    response_data = {
        "cnpj": cnpj_clean,
        "razao_social": razao_social,
        "nome_fantasia": nome_fantasia,
        "setor_principal": cnae_descricao,
        "setor_nome": cnae_descricao,
        "total_contratos_12m": total_12m,
        "valor_total_12m": value_12m,
        "total_contratos_alltime": total_all,
        "valor_total_alltime": value_all,
        "ranking": ranking.model_dump() if ranking else None,
        "top_orgaos": [o.model_dump() for o in _build_top_orgaos(rpc_data)],
        "distribuicao_uf": [d.model_dump() for d in _build_distribuicao_uf(rpc_data)],
        "distribuicao_ano": [d.model_dump() for d in _build_distribuicao_ano(rpc_data)],
        "distribuicao_modalidade": [d.model_dump() for d in _build_distribuicao_modalidade(rpc_data)],
        "generated_at": datetime.now(timezone.utc),
    }

    _set_cached(cnpj_clean, response_data)

    return IntelVitrineResponse(**response_data)


def _build_not_found(cnpj: str) -> dict:
    """Minimal response for CNPJ without data."""
    cnpj_masked = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}"
    return {
        "cnpj": cnpj,
        "razao_social": cnpj_masked,
        "nome_fantasia": None,
        "setor_principal": None,
        "setor_nome": None,
        "total_contratos_12m": 0,
        "valor_total_12m": 0.0,
        "total_contratos_alltime": 0,
        "valor_total_alltime": 0.0,
        "ranking": None,
        "top_orgaos": [],
        "distribuicao_uf": [],
        "distribuicao_ano": [],
        "distribuicao_modalidade": [],
        "generated_at": datetime.now(timezone.utc),
        "aviso_legal": "CNPJ sem contratos registrados.",
    }
