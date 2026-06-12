"""NETINT-008: Pipeline metrics + health aggregation for network intelligence.

Provides the aggregation logic for the /v1/network-intel/health endpoint,
querying Supabase for 24h event counts, opt-in rate, table size, and
cleanup job metadata.
"""

from __future__ import annotations

import logging
from typing import Any

from supabase_client import get_supabase

logger = logging.getLogger(__name__)


async def get_network_health() -> dict[str, Any]:
    """Gather aggregated health metrics for the network intelligence pipeline.

    All queries use direct Supabase query builder (no RPC needed).
    Graceful degradation: if a query fails, returns best-effort data.
    """
    db = get_supabase()
    metrics: dict[str, Any] = {
        "total_events_collected_24h": 0,
        "total_events_discarded_24h": 0,
        "opt_in_rate": 0.0,
        "sanitization_error_rate_24h": 0.0,
        "cleanup_last_run": None,
        "cleanup_last_rows_affected": 0,
        "table_size_mb": 0.0,
    }
    status = "healthy"

    # ── Query 1: Total events in last 24h ──────────────────────────────────
    try:
        from datetime import date, timedelta
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        result = await (
            db.table("network_events_agg")
            .select("contagem")
            .gte("periodo", yesterday)
            .execute()
        )
        if result.data:
            metrics["total_events_collected_24h"] = sum(
                row.get("contagem", 0) or 0 for row in result.data
            )
    except Exception as e:
        logger.warning("network_health: failed to count events (24h): %s", e)
        status = "degraded"

    # ── Query 2: Opt-in rate (users who said yes / total who answered) ─────
    try:
        opt_in_result = await (
            db.table("profiles")
            .select("allow_network_analytics")
            .not_.is_("allow_network_analytics", "null")
            .execute()
        )
        if opt_in_result.data:
            total_answered = len(opt_in_result.data)
            opted_in = sum(
                1 for row in opt_in_result.data if row.get("allow_network_analytics") is True
            )
            if total_answered > 0:
                metrics["opt_in_rate"] = round(opted_in / total_answered, 2)
    except Exception as e:
        logger.warning("network_health: failed to get opt-in rate: %s", e)
        status = "degraded"

    # ── Query 3: Table size in MB ─────────────────────────────────────────
    try:
        # Estimate from supabase table metadata (approximate)
        count_result = await (
            db.table("network_events_agg")
            .select("id", count="exact")
            .limit(0)
            .execute()
        )
        if hasattr(count_result, "count") and count_result.count:
            # Rough estimate: ~200 bytes per row
            metrics["table_size_mb"] = round(count_result.count * 200 / 1048576, 1)
    except Exception as e:
        logger.warning("network_health: failed to estimate table size: %s", e)

    # ── Query 4: Cleanup last run from Prometheus gauges ──────────────────
    try:
        from metrics import NETWORK_CLEANUP_AFFECTED_ROWS
        metrics["cleanup_last_rows_affected"] = int(
            getattr(NETWORK_CLEANUP_AFFECTED_ROWS, "_value", type("", (), {"get": lambda: 0})()).get()
        )
    except Exception:
        pass

    return {"status": status, "metrics": metrics}
