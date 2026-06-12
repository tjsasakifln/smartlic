"""NETINT-007: ARQ weekly cleanup job for network_events aggregation tables.

Runs Sunday at configurable hour (default 03:00 UTC). Performs two operations
in isolated try/except blocks so a failure in step 1 does not prevent step 2:

  1. Weekly rollup: read daily events older than
     NETWORK_EVENTS_AGG_WINDOW_DAYS (default 7), aggregate in-memory by
     ISO week, and upsert into network_events_agg_weekly.

  2. Prune: delete daily records older than
     NETWORK_EVENTS_RETENTION_DAYS (default 365) and weekly records older
     than NETWORK_EVENTS_WEEKLY_RETENTION_DAYS (default 730).

Metrics:
  - smartlic_network_cleanup_affected_rows: gauge set to total affected rows
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from logging import getLogger

from supabase_client import get_supabase

logger = getLogger(__name__)

_DEFAULT_RETENTION_DAYS = 365
_DEFAULT_WEEKLY_RETENTION_DAYS = 730
_DEFAULT_AGG_WINDOW_DAYS = 7


def _to_date(val) -> date | None:
    """Safely convert a value to a date."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _merge_metadados(metadados_list: list[dict]) -> dict:
    """Merge a list of metadados dicts into a single dict with merged arrays."""
    merged: dict[str, set] = {}
    for md in metadados_list:
        if not isinstance(md, dict):
            continue
        for k, v in md.items():
            if k not in merged:
                merged[k] = set()
            if isinstance(v, list):
                merged[k].update(str(item) for item in v)
            elif v is not None:
                merged[k].add(str(v))
    return {k: list(v) if len(v) > 1 else list(v) for k, v in merged.items()}


async def aggregate_and_cleanup_network_events(ctx: dict) -> dict:
    """ARQ cron job: aggregate old events + prune expired records.

    Returns a dict with step outcomes for logging/metrics:

        {
            "weekly_aggregated": int,
            "daily_pruned": int,
            "weekly_pruned": int,
            "error": str | None
        }
    """
    # Load config with graceful fallback.
    # Use os.getenv directly so the value can be patched in tests.
    import os as _os

    _retention_str = _os.getenv("NETWORK_EVENTS_RETENTION_DAYS", str(_DEFAULT_RETENTION_DAYS))
    _window_str = _os.getenv("NETWORK_EVENTS_AGG_WINDOW_DAYS", str(_DEFAULT_AGG_WINDOW_DAYS))
    _weekly_ret_str = _os.getenv("NETWORK_EVENTS_WEEKLY_RETENTION_DAYS", str(_DEFAULT_WEEKLY_RETENTION_DAYS))
    _hour_str = _os.getenv("NETWORK_EVENTS_CLEANUP_HOUR", "3")
    _enabled_str = _os.getenv("NETWORK_EVENTS_CLEANUP_ENABLED", "true")

    NETWORK_EVENTS_RETENTION_DAYS = int(_retention_str)
    NETWORK_EVENTS_AGG_WINDOW_DAYS = int(_window_str)
    NETWORK_EVENTS_WEEKLY_RETENTION_DAYS = int(_weekly_ret_str)
    NETWORK_EVENTS_CLEANUP_ENABLED = _enabled_str.lower() in ("true", "1", "yes")

    result: dict = {
        "weekly_aggregated": 0,
        "daily_pruned": 0,
        "weekly_pruned": 0,
        "error": None,
    }

    if not NETWORK_EVENTS_CLEANUP_ENABLED:
        logger.info("network_events_cleanup: disabled")
        return result

    _ = ctx  # ARQ compatibility
    db = get_supabase()

    # ── Step 1: Weekly rollup ──────────────────────────────────────────────
    cutoff = date.today() - timedelta(days=NETWORK_EVENTS_AGG_WINDOW_DAYS)
    try:
        daily_resp = await db.table("network_events_agg")\
            .select("evento_tipo, dimensao_tipo, dimensao_valor, periodo, contagem, metadados")\
            .lt("periodo", cutoff.isoformat())\
            .execute()
        daily_rows = daily_resp.data if daily_resp and daily_resp.data else []

        if daily_rows:
            weekly: defaultdict = defaultdict(lambda: {"contagem": 0, "metadados": []})
            for row in daily_rows:
                p = _to_date(row.get("periodo"))
                if p is None:
                    continue
                week_start = p - timedelta(days=p.weekday())
                key = (row["evento_tipo"], row["dimensao_tipo"], row["dimensao_valor"], week_start.isoformat())
                weekly[key]["contagem"] += (row.get("contagem") or 0)
                weekly[key]["metadados"].append(row.get("metadados") or {})

            upserted = 0
            for (evt, dim_t, dim_v, wk), agg in weekly.items():
                await db.table("network_events_agg_weekly").upsert({
                    "evento_tipo": evt,
                    "dimensao_tipo": dim_t,
                    "dimensao_valor": dim_v,
                    "semana_inicio": wk,
                    "contagem": agg["contagem"],
                    "metadados": _merge_metadados(agg["metadados"]),
                }, on_conflict=["evento_tipo", "dimensao_tipo", "dimensao_valor", "semana_inicio"]).execute()
                upserted += 1
            result["weekly_aggregated"] = upserted

        logger.info("weekly aggregation: %d rows", result["weekly_aggregated"])
    except Exception as e:
        result["error"] = f"Weekly aggregation failed: {e}"
        logger.error("cleanup step1: %s", result["error"])

    # ── Step 2: Prune ──────────────────────────────────────────────────────
    daily_cutoff = date.today() - timedelta(days=NETWORK_EVENTS_RETENTION_DAYS)
    weekly_cutoff = date.today() - timedelta(days=NETWORK_EVENTS_WEEKLY_RETENTION_DAYS)
    try:
        del_daily = await db.table("network_events_agg").delete().lt("periodo", daily_cutoff.isoformat()).execute()
        result["daily_pruned"] = len(del_daily.data) if del_daily and del_daily.data else 0

        del_weekly = await db.table("network_events_agg_weekly").delete().lt("semana_inicio", weekly_cutoff.isoformat()).execute()
        result["weekly_pruned"] = len(del_weekly.data) if del_weekly and del_weekly.data else 0

        logger.info("prune: daily=%d weekly=%d", result["daily_pruned"], result["weekly_pruned"])
    except Exception as e:
        err = f"Prune step failed: {e}"
        logger.error("cleanup step2: %s", err)
        if result["error"] is None:
            result["error"] = err

    # Prometheus metric
    try:
        from metrics import NETWORK_CLEANUP_AFFECTED_ROWS as gauge
        gauge.set(result["weekly_aggregated"] + result["daily_pruned"] + result["weekly_pruned"])
    except Exception:
        pass

    logger.info("cleanup complete: aggregated=%d pruned_daily=%d pruned_weekly=%d",
                result["weekly_aggregated"], result["daily_pruned"], result["weekly_pruned"])
    return result
