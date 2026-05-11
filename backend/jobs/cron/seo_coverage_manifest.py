"""SEO-COVERAGE-MANIFEST-001: Cron job para popular seo_coverage_manifest.

Roda 3am BRT (6h UTC), após ingestion completa (2am BRT) e purge (4am BRT).
Itera entidades do catálogo e classifica cobertura por tipo:
  full            — atividade nos últimos 6 meses
  partial         — atividade entre 6-24 meses atrás
  historical_empty— atividade > 24 meses ou nunca (mas slug existe no catálogo)
  empty           — nunca teve dados conhecidos

Fonte de dados: MVs existentes (mv_sitemap_cnpjs, mv_sitemap_orgaos,
mv_sitemap_fornecedores) + queries diretas para municípios e itens.
"""

import asyncio
import logging
from datetime import datetime, timezone

import sentry_sdk

logger = logging.getLogger(__name__)

SEO_MANIFEST_INTERVAL_S = 24 * 60 * 60  # 24h


async def run_seo_coverage_manifest() -> dict:
    """Popula seo_coverage_manifest com status de cobertura por entidade."""
    from supabase_client import get_supabase

    sb = get_supabase()
    stats: dict[str, int] = {}

    try:
        # --- Municípios: verifica quais slugs têm licitações no datalake ---
        from routes.municipios_publicos import _MUNICIPIOS

        municipio_slugs = [m[0] for m in _MUNICIPIOS]
        municipio_ibge = {m[0]: m[3] for m in _MUNICIPIOS}  # slug → uf

        # Query agregada: 1 query, não N+1
        result = await asyncio.to_thread(
            lambda: sb.rpc(
                "get_municipio_coverage_summary",
                {},
            ).execute()
        )

        covered_slugs: dict[str, datetime | None] = {}
        if result.data:
            for row in result.data:
                covered_slugs[row["slug"]] = row.get("last_activity_at")
        else:
            # Fallback: query direta sem RPC
            now = datetime.now(timezone.utc)
            raw = await asyncio.to_thread(
                lambda: sb.table("pncp_raw_bids")
                .select("municipio_nome, uf, data_publicacao")
                .order("data_publicacao", desc=True)
                .limit(50000)
                .execute()
            )
            for row in (raw.data or []):
                uf = row.get("uf", "")
                nome = row.get("municipio_nome", "")
                if nome and uf:
                    slug = f"{nome.lower().replace(' ', '-').replace('/', '-')}-{uf.lower()}"
                    if slug not in covered_slugs:
                        covered_slugs[slug] = row.get("data_publicacao")

        now = datetime.now(timezone.utc)
        upsert_rows = []
        for slug in municipio_slugs:
            last_activity = covered_slugs.get(slug)
            if last_activity is None:
                status = "empty"
                last_at = None
            else:
                if isinstance(last_activity, str):
                    try:
                        from datetime import datetime as dt
                        last_activity = dt.fromisoformat(last_activity.replace("Z", "+00:00"))
                    except Exception:
                        last_activity = None
                if last_activity is None:
                    status = "historical_empty"
                    last_at = None
                else:
                    age_days = (now - last_activity).days
                    if age_days <= 180:
                        status = "full"
                    elif age_days <= 730:
                        status = "partial"
                    else:
                        status = "historical_empty"
                    last_at = last_activity.isoformat()

            upsert_rows.append({
                "entity_type": "municipio",
                "entity_id": slug,
                "coverage_status": status,
                "last_activity_at": last_at,
                "updated_at": now.isoformat(),
            })

        if upsert_rows:
            # Batch upsert — split 500/batch to avoid payload limits
            for i in range(0, len(upsert_rows), 500):
                batch = upsert_rows[i:i + 500]
                await asyncio.to_thread(
                    lambda b=batch: sb.table("seo_coverage_manifest")
                    .upsert(b, on_conflict="entity_type,entity_id")
                    .execute()
                )

        stats["municipios_processed"] = len(upsert_rows)
        stats["municipios_full"] = sum(1 for r in upsert_rows if r["coverage_status"] == "full")
        stats["municipios_empty"] = sum(1 for r in upsert_rows if r["coverage_status"] == "empty")

        logger.info(
            "seo_coverage_manifest: municipios processed=%d full=%d empty=%d",
            stats["municipios_processed"],
            stats["municipios_full"],
            stats["municipios_empty"],
        )

    except Exception as exc:
        logger.error("seo_coverage_manifest municípios failed: %s", exc)
        sentry_sdk.capture_exception(exc)
        stats["municipios_error"] = str(exc)

    stats["status"] = "ok" if "municipios_error" not in stats else "partial_error"
    return stats


async def _seo_coverage_manifest_loop() -> None:
    """Background loop: run diariamente ~3am BRT (após startup delay)."""
    import time
    from datetime import datetime, timezone

    # Alinhar para próximo 6h UTC (= 3am BRT)
    now = datetime.now(timezone.utc)
    next_run_hour = 6
    seconds_to_next = ((next_run_hour - now.hour) % 24) * 3600 - now.minute * 60 - now.second
    if seconds_to_next <= 0:
        seconds_to_next += 86400
    # Cap: se próxima execução > 24h, rodar em 1h para bootstrap
    if seconds_to_next > 23 * 3600:
        seconds_to_next = 3600

    logger.info("seo_coverage_manifest: first run in %.0fs", seconds_to_next)
    await asyncio.sleep(seconds_to_next)

    while True:
        result = await run_seo_coverage_manifest()
        logger.info("seo_coverage_manifest completed: %s", result)
        await asyncio.sleep(SEO_MANIFEST_INTERVAL_S)


async def start_seo_coverage_manifest_task() -> asyncio.Task:
    """Cria e retorna a task background."""
    return asyncio.create_task(_seo_coverage_manifest_loop())
