"""cache/cascade.py — Unified cascade read: L2(Redis) → L1(Supabase) → L3(Local) → Global.

Extracted from cache/manager.py (DEBT-203) to keep manager.py ≤ 600 LOC.
Public API: get_from_cache_cascade
"""
import json
import logging
from typing import Optional

from utils.error_reporting import report_error
from metrics import CACHE_HITS as METRICS_CACHE_HITS, CACHE_MISSES as METRICS_CACHE_MISSES

import cache.redis as _redis
import cache.local_file as _local
import cache.supabase as _supa
from cache.enums import (
    CacheLevel,
    compute_search_hash,
    compute_search_hash_without_dates,
)
from cache._ops import _process_cache_hit, _process_cache_hit_allow_expired

logger = logging.getLogger(__name__)


def _all_sources_down() -> bool:
    """CRIT-081: Check if all data source circuit breakers are open/degraded."""
    try:
        from pncp_client import get_circuit_breaker
        cb_pncp = get_circuit_breaker("pncp")
        cb_pcp = get_circuit_breaker("pcp")
        cb_comprasgov = get_circuit_breaker("comprasgov")
        return (
            cb_pncp.is_degraded
            and cb_pcp.is_degraded
            and cb_comprasgov.is_degraded
        )
    except Exception:
        return False


def _format_cache_date_range(cached_at: "str | None") -> "str | None":
    """STORY-306 AC5: Format cache date range for user display."""
    if not cached_at:
        return None
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return cached_at


async def get_from_cache_cascade(
    user_id: str,
    params: dict,
    *,
    allow_expired: bool = False,
) -> Optional[dict]:
    """Unified cache cascade: L2 (InMemory/Redis) → L1 (Supabase) → L3 (Local file)."""
    params_hash = compute_search_hash(params)

    _hit_fn = _process_cache_hit_allow_expired if allow_expired else _process_cache_hit

    result = await _cascade_read_levels(user_id, params_hash, params, _hit_fn)
    if result:
        return result

    from config import CACHE_LEGACY_KEY_FALLBACK
    if CACHE_LEGACY_KEY_FALLBACK:
        legacy_hash = compute_search_hash_without_dates(params)
        if legacy_hash != params_hash:
            result = await _cascade_read_levels(user_id, legacy_hash, params, _hit_fn)
            if result:
                result["cache_fallback"] = True
                cached_at = result.get("cached_at")
                result["cache_date_range"] = _format_cache_date_range(cached_at)
                logger.info(
                    f"Cascade HIT via legacy key (without dates) for hash "
                    f"{legacy_hash[:12]}... (fallback from {params_hash[:12]})"
                )
                return result

    if not allow_expired:
        try:
            from config import SERVE_EXPIRED_CACHE_ON_TOTAL_OUTAGE
            if SERVE_EXPIRED_CACHE_ON_TOTAL_OUTAGE and _all_sources_down():
                logger.warning(
                    "CRIT-081: All sources down — retrying cascade with allow_expired=True "
                    "for hash %s...",
                    params_hash[:12],
                )
                result = await _cascade_read_levels(
                    user_id, params_hash, params, _process_cache_hit_allow_expired
                )
                if result:
                    result["is_stale_fallback"] = True
                    METRICS_CACHE_HITS.labels(
                        level=str(result.get("cache_level", "unknown")),
                        freshness="expired_outage",
                    ).inc()
                    logger.warning(json.dumps({
                        "event": "cache_expired_served_total_outage",
                        "cache_key": params_hash[:12],
                        "cache_age_hours": result.get("cache_age_hours"),
                        "results_count": len(result.get("results", [])),
                    }))
                    return result
        except Exception as e:
            logger.debug("CRIT-081: total-outage expired fallback check failed: %s", e)

    METRICS_CACHE_MISSES.labels(level="cascade").inc()
    return None


async def _cascade_read_levels(
    user_id: str,
    params_hash: str,
    params: dict,
    _hit_fn,
) -> Optional[dict]:
    """STORY-306: Read cache across cascade levels (L2→L1→L3→Global) for a given hash key."""
    _level_str = {
        CacheLevel.REDIS: "memory",
        CacheLevel.SUPABASE: "supabase",
        CacheLevel.LOCAL: "local",
    }

    # L2: Redis/InMemory — O(1) lookup, no I/O
    try:
        data = _redis._get_from_redis(params_hash)
        if data:
            result = _hit_fn(data, params_hash, CacheLevel.REDIS)
            if result:
                result["cache_level"] = _level_str[CacheLevel.REDIS]
                _freshness = result.get("cache_status", "stale")
                METRICS_CACHE_HITS.labels(level="memory", freshness=_freshness).inc()
                return result
    except Exception as e:
        logger.warning(f"Cascade L2/redis read failed: {e}")

    # L1: Supabase — HTTP roundtrip (~100-300ms)
    try:
        data = await _supa._get_from_supabase(user_id, params_hash)
        if data:
            result = _hit_fn(data, params_hash, CacheLevel.SUPABASE)
            if result:
                result["cache_level"] = _level_str[CacheLevel.SUPABASE]
                _freshness = result.get("cache_status", "stale")
                METRICS_CACHE_HITS.labels(level="supabase", freshness=_freshness).inc()
                return result
    except Exception as e:
        report_error(
            e, f"Cascade L1/supabase read failed (key={params_hash[:12]})",
            expected=True, tags={"cache_operation": "cascade_read", "cache_level": "supabase"}, log=logger,
        )

    # L3: Local file — disk I/O (~5-20ms)
    try:
        data = _local._get_from_local(params_hash)
        if data:
            result = _hit_fn(data, params_hash, CacheLevel.LOCAL)
            if result:
                result["cache_level"] = _level_str[CacheLevel.LOCAL]
                _freshness = result.get("cache_status", "stale")
                METRICS_CACHE_HITS.labels(level="local", freshness=_freshness).inc()
                logger.info(json.dumps({
                    "event": "cache_l3_served",
                    "cache_key": params_hash[:12],
                    "cache_age_hours": result["cache_age_hours"],
                    "results_count": len(result["results"]),
                }))
                return result
    except Exception as e:
        logger.error(f"Cascade L3/local read failed: {e}")

    # GTM-ARCH-002 AC1: Global cross-user fallback before cascade miss
    try:
        global_data = await _supa._get_global_fallback_from_supabase(params)
        if global_data:
            result = _hit_fn(global_data, params_hash, CacheLevel.SUPABASE)
            if result:
                result["cache_level"] = "global"
                METRICS_CACHE_HITS.labels(level="global", freshness=result.get("cache_status", "stale")).inc()
                logger.info(json.dumps({
                    "event": "cache_global_fallback_served",
                    "cache_key": params_hash[:12],
                    "cache_age_hours": result["cache_age_hours"],
                    "results_count": len(result["results"]),
                }))
                return result
    except Exception as e:
        logger.debug(f"Cascade global fallback failed: {e}")

    return None
