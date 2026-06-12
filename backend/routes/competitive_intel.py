"""COMPINT-010/013/014: Competitive Intelligence vertical endpoints.

Endpoints:
  GET  /v1/intel-concorrente/landscape       — COMPINT-010: Competitive landscape
  GET  /v1/intel-concorrente/territory/{cnpj} — COMPINT-010: Territory map
  GET  /v1/intel-concorrente/benchmarks       — COMPINT-013: Sector benchmarks
  POST /v1/intel-concorrente/dossie/{cnpj}    — COMPINT-014: Generate dossie PDF
  GET  /v1/intel-concorrente/dossie/{cnpj}/{job_id}/status — COMPINT-014: Dossie status
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import Response

from quota import get_competitive_intel_dependency
from sectors import SECTORS

from schemas.competitive_intel import (
    BenchmarkPercentile,
    CompetitiveLandscapeResponse,
    CompetitorBenchmark,
    CompetitorItem,
    DossieRequest,
    DossieResponse,
    DossieStatusResponse,
    SectorBenchmarkResponse,
    TerritoryData,
    TerritoryUfData,
    AlertaPosicionamento,
    ConcorrenteInfo,
    FornecedorIntelResponse,
    TerritorioStats,
    WinMetrics,
)

# COMPINT-011 (#1663): Supplier-level schemas
from supabase_client import get_supabase, sb_execute  # noqa: F811

logger = logging.getLogger(__name__)

router = APIRouter(tags=["competitive_intel"])

# Gate dependency
_comp_intel = get_competitive_intel_dependency()

# Cache config
_CACHE_TTL_SECONDS = 4 * 60 * 60  # 4h
_NEGATIVE_CACHE_TTL = 300  # 5min for empty results
_intel_cache: dict[str, tuple[dict, float]] = {}

# Dossie job store (in-memory; production would use ARQ/Redis)
_dossie_jobs: dict[str, dict] = {}

_VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
    "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
    "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
}
_DEFAULT_MONTHS = 12


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _get_cached(key: str) -> Optional[dict]:
    entry = _intel_cache.get(key)
    if entry:
        data, ts = entry
        if time.time() - ts < _CACHE_TTL_SECONDS:
            return data
        _intel_cache.pop(key, None)
    return None


def _set_cached(key: str, data: dict, negative: bool = False) -> None:
    ttl = _NEGATIVE_CACHE_TTL if negative else _CACHE_TTL_SECONDS
    _intel_cache[key] = (data, time.time() + ttl)


# ---------------------------------------------------------------------------
# Mock data helpers (MVP phase — uses in-memory aggregation from supabase)
# ---------------------------------------------------------------------------


async def _fetch_landscape(setor_id: str, uf: Optional[str]) -> CompetitiveLandscapeResponse:
    """Fetch competitive landscape from pncp_supplier_contracts."""

    sb = get_supabase()
    sector = SECTORS.get(setor_id)
    sector_name = sector.name if sector else setor_id
    keywords = list(sector.keywords) if sector else []

    now = datetime.now(timezone.utc)
    data_inicial = (now - timedelta(days=_DEFAULT_MONTHS * 30)).strftime("%Y-%m-%d")

    # Query aggregate data per supplier
    query = (
        sb.table("pncp_supplier_contracts")
        .select("ni_fornecedor,nome_fornecedor,valor_global,uf,data_assinatura")
        .gte("data_assinatura", data_inicial)
        .order("valor_global", desc=True)
    )
    if uf:
        query = query.eq("uf", uf)

    resp = await sb_execute(query, category="rpc")
    rows = resp.data or []
    if not rows:
        return CompetitiveLandscapeResponse(
            setor_id=setor_id, setor_nome=sector_name, uf=uf,
            total_contratado=0, total_contratos=0, total_concorrentes=0,
            periodo=f"Ultimos {_DEFAULT_MONTHS} meses",
        )

    # Simple keyword filter by objeto_contrato if available
    if "objeto_contrato" in rows[0] if rows else False:
        rows = [r for r in rows if any(kw.lower() in (r.get("objeto_contrato") or "").lower() for kw in keywords)]

    # Aggregate by supplier
    agg: dict[str, dict] = {}
    for r in rows:
        cnpj = r.get("ni_fornecedor", "")
        nome = r.get("nome_fornecedor", "N/D")
        valor = float(r.get("valor_global", 0) or 0)
        row_uf = r.get("uf", "")
        if cnpj not in agg:
            agg[cnpj] = {"nome": nome, "total": 0, "count": 0, "ufs": set()}
        agg[cnpj]["total"] += valor
        agg[cnpj]["count"] += 1
        if row_uf:
            agg[cnpj]["ufs"].add(row_uf)

    total_value = sum(a["total"] for a in agg.values())
    items: list[CompetitorItem] = []
    sorted_suppliers = sorted(agg.values(), key=lambda x: x["total"], reverse=True)

    for s in sorted_suppliers[:20]:
        share = (s["total"] / total_value * 100) if total_value > 0 else 0
        ticket = s["total"] / s["count"] if s["count"] > 0 else 0
        items.append(CompetitorItem(
            cnpj="",
            razao_social=s["nome"],
            total_contratado=round(s["total"], 2),
            numero_contratos=s["count"],
            ticket_medio=round(ticket, 2),
            ufs_atuacao=sorted(s["ufs"]),
            market_share=round(share, 1),
            tendencia="estavel",
        ))

    return CompetitiveLandscapeResponse(
        setor_id=setor_id,
        setor_nome=sector_name,
        uf=uf,
        total_contratado=round(total_value, 2),
        total_contratos=sum(a["count"] for a in agg.values()),
        total_concorrentes=len(agg),
        top_concorrentes=items,
        periodo=f"Ultimos {_DEFAULT_MONTHS} meses",
    )


async def _fetch_territory(cnpj: str) -> TerritoryData:
    """Fetch territory data for a specific competitor from pncp_supplier_contracts."""

    sb = get_supabase()
    now = datetime.now(timezone.utc)
    data_inicial = (now - timedelta(days=_DEFAULT_MONTHS * 30)).strftime("%Y-%m-%d")

    query = (
        sb.table("pncp_supplier_contracts")
        .select("valor_global,uf,nome_fornecedor")
        .gte("data_assinatura", data_inicial)
        .eq("is_active", True)
    )
    # Try matching by CNPJ parts
    cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "")
    query = query.ilike("ni_fornecedor", f"%{cnpj_clean}%")

    resp = await sb_execute(query, category="rpc")
    rows = resp.data or []

    if not rows:
        return TerritoryData(
            cnpj=cnpj,
            razao_social="Fornecedor nao encontrado",
            total_contratado=0,
            total_contratos=0,
            ufs=[],
        )

    nome = rows[0].get("nome_fornecedor", "N/D") if rows else "N/D"

    uf_agg: dict[str, dict] = defaultdict(lambda: {"total": 0, "count": 0, "orgaos": []})
    for r in rows:
        uf_key = r.get("uf", "BR")
        valor = float(r.get("valor_global", 0) or 0)
        uf_agg[uf_key]["total"] += valor
        uf_agg[uf_key]["count"] += 1

    total_value = sum(a["total"] for a in uf_agg.values())
    ufs_data: list[TerritoryUfData] = []
    for uf_key, data in sorted(uf_agg.items(), key=lambda x: x[1]["total"], reverse=True):
        share = (data["total"] / total_value * 100) if total_value > 0 else 0
        ufs_data.append(TerritoryUfData(
            uf=uf_key,
            total_contratado=round(data["total"], 2),
            numero_contratos=data["count"],
            market_share=round(share, 1),
            orgaos_principais=data["orgaos"][:5],
        ))

    total_contracts = sum(a["count"] for a in uf_agg.values())
    return TerritoryData(
        cnpj=cnpj,
        razao_social=nome,
        total_contratado=round(total_value, 2),
        total_contratos=total_contracts,
        ufs=ufs_data,
    )


async def _fetch_benchmarks(cnpj: str, setor_id: str) -> SectorBenchmarkResponse:
    """Fetch sector benchmarks for a competitor."""

    sb = get_supabase()
    sector = SECTORS.get(setor_id)
    sector_name = sector.name if sector else setor_id

    now = datetime.now(timezone.utc)
    data_inicial = (now - timedelta(days=_DEFAULT_MONTHS * 30)).strftime("%Y-%m-%d")

    # Get the competitor's aggregated data
    cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "")
    comp_query = (
        sb.table("pncp_supplier_contracts")
        .select("valor_global")
        .gte("data_assinatura", data_inicial)
        .eq("is_active", True)
        .ilike("ni_fornecedor", f"%{cnpj_clean}%")
    )
    comp_resp = await sb_execute(comp_query, category="rpc")
    comp_rows = comp_resp.data or []
    comp_ticket = sum(float(r.get("valor_global", 0) or 0) for r in comp_rows) / max(len(comp_rows), 1)

    # Get sector-wide data
    sector_query = (
        sb.table("pncp_supplier_contracts")
        .select("valor_global,ni_fornecedor")
        .gte("data_assinatura", data_inicial)
        .eq("is_active", True)
        .order("valor_global", desc=True)
    )
    sector_resp = await sb_execute(sector_query, category="rpc")
    sector_rows = sector_resp.data or []

    sector_values = [float(r.get("valor_global", 0) or 0) for r in sector_rows if float(r.get("valor_global", 0) or 0) > 0]
    sector_values.sort()

    def percentile(data: list[float], p: float) -> float:
        if not data:
            return 0
        idx = int(len(data) * p / 100)
        return data[min(idx, len(data) - 1)]

    p25 = percentile(sector_values, 25)
    p50 = percentile(sector_values, 50)
    p75 = percentile(sector_values, 75)

    comp_percentile = 50  # approximate
    if sector_values:
        below = sum(1 for v in sector_values if v <= comp_ticket)
        comp_percentile = round(below / len(sector_values) * 100)

    metricas = [
        CompetitorBenchmark(
            metrica="ticket_medio",
            label="Ticket Medio",
            valor_concorrente=round(comp_ticket, 2),
            percentil_concorrente=comp_percentile,
            benchmark_setor=BenchmarkPercentile(p25=round(p25, 2), p50=round(p50, 2), p75=round(p75, 2)),
            descricao=f"Este player esta no percentil {comp_percentile} de ticket medio.",
        ),
        CompetitorBenchmark(
            metrica="total_contratos",
            label="Total de Contratos",
            valor_concorrente=len(comp_rows),
            percentil_concorrente=comp_percentile,
            benchmark_setor=BenchmarkPercentile(
                p25=round(percentile(sector_values, 25), 2),
                p50=round(percentile(sector_values, 50), 2),
                p75=round(percentile(sector_values, 75), 2),
            ),
            descricao=f"Total de contratos do concorrente: {len(comp_rows)}.",
        ),
    ]

    razao = comp_rows[0].get("nome_fornecedor", "Concorrente") if comp_rows else "Concorrente"
    return SectorBenchmarkResponse(
        cnpj=cnpj,
        razao_social=razao,
        setor_id=setor_id,
        setor_nome=sector_name,
        metricas=metricas,
    )


# ---------------------------------------------------------------------------
# COMPINT-010: GET /v1/intel-concorrente/landscape
# ---------------------------------------------------------------------------


@router.get(
    "/intel-concorrente/landscape",
    summary="Competitive Landscape — top players in a sector",
    response_model=CompetitiveLandscapeResponse,
    dependencies=[Depends(_comp_intel)],
)
async def get_competitive_landscape(
    setor: str = Query(..., description="ID do setor (ex: ti, saude, construcao)"),
    uf: Optional[str] = Query(default=None, description="UF (2 letras, opcional)"),
):
    sector_config = SECTORS.get(setor)
    if sector_config is None:
        raise HTTPException(status_code=400, detail=f"Setor invalido: '{setor}'")

    uf_clean = uf.strip().upper() if uf else None
    if uf_clean and uf_clean not in _VALID_UFS:
        raise HTTPException(status_code=400, detail=f"UF invalida: '{uf}'")

    cache_key = f"landscape:{setor}:{uf_clean or 'BR'}"
    cached = _get_cached(cache_key)
    if cached:
        return CompetitiveLandscapeResponse(**cached)

    result = await _fetch_landscape(setor, uf_clean)
    _set_cached(cache_key, result.model_dump())
    return result


# ---------------------------------------------------------------------------
# COMPINT-010: GET /v1/intel-concorrente/territory/{cnpj}
# ---------------------------------------------------------------------------


@router.get(
    "/intel-concorrente/territory/{cnpj}",
    summary="Territory Map — competitor geographic presence",
    response_model=TerritoryData,
    dependencies=[Depends(_comp_intel)],
)
async def get_competitor_territory(
    cnpj: str = Path(..., description="CNPJ do concorrente (com ou sem mascara)"),
):
    cache_key = f"territory:{cnpj}"
    cached = _get_cached(cache_key)
    if cached:
        return TerritoryData(**cached)

    result = await _fetch_territory(cnpj)
    _set_cached(cache_key, result.model_dump())
    return result


# ---------------------------------------------------------------------------
# COMPINT-013: GET /v1/intel-concorrente/benchmarks
# ---------------------------------------------------------------------------


@router.get(
    "/intel-concorrente/benchmarks",
    summary="Sector Benchmarks — competitive performance comparison",
    response_model=SectorBenchmarkResponse,
    dependencies=[Depends(_comp_intel)],
)
async def get_competitor_benchmarks(
    cnpj: str = Query(..., description="CNPJ do concorrente"),
    setor: str = Query(..., description="ID do setor para benchmark"),
):
    if setor not in SECTORS:
        raise HTTPException(status_code=400, detail=f"Setor invalido: '{setor}'")

    cache_key = f"benchmarks:{cnpj}:{setor}"
    cached = _get_cached(cache_key)
    if cached:
        return SectorBenchmarkResponse(**cached)

    result = await _fetch_benchmarks(cnpj, setor)
    _set_cached(cache_key, result.model_dump())
    return result


# ---------------------------------------------------------------------------
# COMPINT-014: POST /v1/intel-concorrente/dossie/{cnpj}
# ---------------------------------------------------------------------------


@router.post(
    "/intel-concorrente/dossie/{cnpj}",
    summary="Generate Competitive Dossie PDF",
    response_model=DossieResponse,
    dependencies=[Depends(_comp_intel)],
)
async def generate_competitive_dossie(
    cnpj: str = Path(..., description="CNPJ do concorrente"),
    body: Optional[DossieRequest] = None,
):
    job_id = str(uuid4())
    _dossie_jobs[job_id] = {
        "cnpj": cnpj,
        "status": "queued",
        "progress": 0,
        "download_url": None,
        "error": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # In MVP: generate synchronously (in production, dispatch to ARQ)
    try:
        from pdf_generator_competitive_dossie import generate_competitive_dossie_report
        from supabase_client import get_supabase

        _dossie_jobs[job_id]["status"] = "processing"
        _dossie_jobs[job_id]["progress"] = 50

        sb = get_supabase()
        pdf_bio = await asyncio.to_thread(
            generate_competitive_dossie_report,
            sb, cnpj,
            body.setor_id if body else None,
            body.include_llm_summary if body else True,
        )
        pdf_bytes = pdf_bio.getvalue()

        # Store as response
        download_url = f"/intel-concorrente/dossie/{cnpj}/{job_id}/download"
        _dossie_jobs[job_id].update({
            "status": "done",
            "progress": 100,
            "download_url": download_url,
            "pdf_bytes": pdf_bytes,
        })
    except Exception as e:
        logger.error("Dossie generation failed for cnpj=%s: %s", cnpj, e)
        _dossie_jobs[job_id].update({
            "status": "error",
            "error": str(e),
        })

    return DossieResponse(
        cnpj=cnpj,
        job_id=job_id,
        status=_dossie_jobs[job_id]["status"],
        download_url=_dossie_jobs[job_id].get("download_url"),
    )


# ---------------------------------------------------------------------------
# COMPINT-014: GET /v1/intel-concorrente/dossie/{cnpj}/{job_id}/status
# ---------------------------------------------------------------------------


@router.get(
    "/intel-concorrente/dossie/{cnpj}/{job_id}/status",
    summary="Check Dossie generation status",
    response_model=DossieStatusResponse,
    dependencies=[Depends(_comp_intel)],
)
async def get_dossie_status(
    cnpj: str = Path(...),
    job_id: str = Path(...),
):
    job = _dossie_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")

    return DossieStatusResponse(
        cnpj=job["cnpj"],
        job_id=job_id,
        status=job["status"],
        progress=job.get("progress", 0),
        download_url=job.get("download_url"),
        error=job.get("error"),
    )


# ---------------------------------------------------------------------------
# COMPINT-014: GET /v1/intel-concorrente/dossie/{cnpj}/{job_id}/download
# ---------------------------------------------------------------------------


@router.get(
    "/intel-concorrente/dossie/{cnpj}/{job_id}/download",
    summary="Download the generated Dossie PDF",
    response_model=None,
    dependencies=[Depends(_comp_intel)],
)
async def download_dossie(
    cnpj: str = Path(...),
    job_id: str = Path(...),
):
    job = _dossie_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nao encontrado")
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="PDF ainda nao gerado")

    pdf_bytes = job.get("pdf_bytes")
    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="PDF nao disponivel")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="dossie-{cnpj}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )





# ============================================================================
# COMPINT-011 (#1663): Fornecedor Competitive Intelligence
# ============================================================================


def _derive_alertas(
    territorio: list[dict],
    stats: dict,
) -> list[dict]:
    """Derive positioning alerts from territory data."""
    alertas: list[dict] = []

    expanding_ufs = [
        t for t in territorio
        if t.get("tendencia") in ("crescendo", "expansao", "nova")
    ]
    if expanding_ufs:
        nomes = [t["uf"] for t in expanding_ufs[:3]]
        alertas.append({
            "tipo": "expansao",
            "mensagem": f"Expandindo atuação para {'/'.join(nomes)}",
            "severidade": "info",
        })

    crescimento = stats.get("crescimento_anual")
    if crescimento is not None:
        if crescimento > 30:
            alertas.append({
                "tipo": "crescimento",
                "mensagem": f"Crescimento de {crescimento:.0f}% em contratos no último ano",
                "severidade": "success",
            })
        elif crescimento > 10:
            alertas.append({
                "tipo": "crescimento",
                "mensagem": f"Crescimento de {crescimento:.0f}% em contratos",
                "severidade": "info",
            })
        elif crescimento < -10:
            alertas.append({
                "tipo": "crescimento",
                "mensagem": f"Retração de {abs(crescimento):.0f}% em contratos no último ano",
                "severidade": "warning",
            })

    dominant_ufs = [
        t for t in territorio
        if t.get("market_share_uf") is not None and t["market_share_uf"] > 0.3
    ]
    if dominant_ufs:
        top = max(dominant_ufs, key=lambda t: t["market_share_uf"])
        share_pct = top["market_share_uf"] * 100
        alertas.append({
            "tipo": "dominio",
            "mensagem": f"Player dominante em {top['uf']} com {share_pct:.0f}% de market share",
            "severidade": "success",
        })

    return alertas


def _extract_territorio(raw: list) -> list[dict]:
    """Normalize territory entries from RPC output."""
    return [
        {
            "uf": t.get("uf", ""),
            "contratos": t.get("contratos", 0) or 0,
            "valor_total": float(t.get("valor_total", 0) or 0),
            "ticket_medio_uf": float(t.get("ticket_medio_uf", 0) or 0),
            "orgaos_principais": t.get("orgaos_principais", []),
            "market_share_uf": (
                float(t["market_share_uf"])
                if t.get("market_share_uf") is not None
                else None
            ),
            "tendencia": t.get("tendencia"),
        }
        for t in (raw or [])
    ]


def _extract_orgaos(raw: list) -> list[dict]:
    """Normalize orgaos_favoritos from RPC output."""
    return [
        {
            "orgao_nome": o.get("orgao_nome", ""),
            "contratos": o.get("contratos", 0) or 0,
            "valor_total": float(o.get("valor_total", 0) or 0),
            "categorias": o.get("categorias", []),
            "ultima_vitoria": o.get("ultima_vitoria"),
            "frequencia_anual": (
                float(o["frequencia_anual"])
                if o.get("frequencia_anual") is not None
                else None
            ),
        }
        for o in (raw or [])
    ]


@router.get(
    "/intel-concorrente/fornecedor/{cnpj}",
    summary="Competitive Intelligence data for a supplier CNPJ (COMPINT-011)",
    response_model=FornecedorIntelResponse,
)
async def fornecedor_competitive_intel(
    cnpj: str = Path(..., description="Supplier CNPJ (14 digits)"),
    anos: int = 3,
    user: dict = Depends(get_competitive_intel_dependency()),
):
    """Return competitive intelligence data for *cnpj*."""
    cnpj_clean = "".join(c for c in cnpj if c.isdigit())
    if len(cnpj_clean) != 14:
        raise HTTPException(
            status_code=400,
            detail="CNPJ inválido: deve conter 14 dígitos.",
        )

    sb = get_supabase()
    now_iso = datetime.now(timezone.utc).isoformat()

    try:
        territory_resp = await sb_execute(
            sb.rpc("competitor_territory_map", {
                "p_cnpj": cnpj_clean,
                "p_anos": anos,
            })
        )
        territory_data = territory_resp.data
    except Exception as exc:
        logger.error("competitor_territory_map RPC failed for %s: %s", cnpj_clean, exc)
        raise HTTPException(
            status_code=502,
            detail="Falha ao buscar dados territoriais do concorrente.",
        )

    if not territory_data or isinstance(territory_data, dict) and "erro" in territory_data:
        raise HTTPException(
            status_code=404,
            detail="Dados de inteligência concorrencial não disponíveis para este CNPJ.",
        )

    win_metrics_raw: Optional[dict] = None
    try:
        win_resp = await sb_execute(
            sb.rpc("competitor_win_metrics", {
                "p_cnpj": cnpj_clean,
                "p_anos": anos,
            })
        )
        win_data = win_resp.data
        if isinstance(win_data, dict) and "win_metrics" in win_data:
            win_metrics_raw = win_data["win_metrics"]
    except Exception as exc:
        logger.warning("competitor_win_metrics RPC failed for %s: %s", cnpj_clean, exc)

    concorrente_raw = territory_data.get("concorrente", {})
    territorio_raw = territory_data.get("territorio", [])
    orgaos_raw = territory_data.get("orgaos_favoritos", [])
    stats_raw = territory_data.get("stats", {})

    territorio = _extract_territorio(territorio_raw)
    orgaos_favoritos = _extract_orgaos(orgaos_raw)
    alertas_raw = _derive_alertas(territorio_raw, stats_raw)

    win_metrics: Optional[WinMetrics] = None
    if win_metrics_raw:
        win_metrics = WinMetrics(
            taxa_vitoria_estimada=win_metrics_raw.get("taxa_vitoria_estimada"),
            velocidade_crescimento=win_metrics_raw.get("velocidade_crescimento"),
            tendencia=win_metrics_raw.get("tendencia"),
            ticket_p25=(
                float(win_metrics_raw["ticket_p25"])
                if win_metrics_raw.get("ticket_p25") is not None
                else None
            ),
            ticket_p50=(
                float(win_metrics_raw["ticket_p50"])
                if win_metrics_raw.get("ticket_p50") is not None
                else None
            ),
            ticket_p75=(
                float(win_metrics_raw["ticket_p75"])
                if win_metrics_raw.get("ticket_p75") is not None
                else None
            ),
            ticket_p90=(
                float(win_metrics_raw["ticket_p90"])
                if win_metrics_raw.get("ticket_p90") is not None
                else None
            ),
            indice_concentracao=win_metrics_raw.get("indice_concentracao"),
            dependencia_publica=win_metrics_raw.get("dependencia_publica"),
        )

    return FornecedorIntelResponse(
        concorrente=ConcorrenteInfo(
            cnpj=concorrente_raw.get("cnpj", cnpj_clean),
            nome=concorrente_raw.get("nome", ""),
            total_contratos=concorrente_raw.get("total_contratos", 0) or 0,
            ticket_medio=float(concorrente_raw.get("ticket_medio", 0) or 0),
            ticket_mediana=float(concorrente_raw.get("ticket_mediana", 0) or 0),
            valor_total_contratado=float(
                concorrente_raw.get("valor_total_contratado", 0) or 0
            ),
        ),
        territorio=territorio,
        orgaos_favoritos=orgaos_favoritos,
        stats=TerritorioStats(
            ufs_atuacao=stats_raw.get("ufs_atuacao", 0) or 0,
            orgaos_unicos=stats_raw.get("orgaos_unicos", 0) or 0,
            anos_atuacao=stats_raw.get("anos_atuacao", 0) or 0,
            crescimento_anual=(
                float(stats_raw["crescimento_anual"])
                if stats_raw.get("crescimento_anual") is not None
                else None
            ),
            tendencia_posicionamento=stats_raw.get("tendencia_posicionamento"),
        ),
        win_metrics=win_metrics,
        alertas=[AlertaPosicionamento(**a) for a in alertas_raw],
        feature_enabled=True,
        generated_at=now_iso,
    )
