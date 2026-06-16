"""cache/_ops.py — Cache hit processing, tracking, and degradation ops.

Extracted from cache/manager.py to keep manager.py under 600 LOC.
These are called by manager.py and re-exported via search_cache facade.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from cache.enums import (
    CacheLevel, CacheStatus, CachePriority,
    CACHE_FRESH_HOURS, CACHE_STALE_HOURS,
    classify_priority, calculate_backoff_minutes,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Cache key degradation tracking (B-03)
# ============================================================================


async def record_cache_fetch_failure(user_id: str, params_hash: str) -> dict:
    """B-03 AC3: Record a fetch failure for a cache key."""
    from supabase_client import get_supabase, sb_execute
    sb = get_supabase()

    now = datetime.now(timezone.utc)

    response = await sb_execute(
        sb.table("search_results_cache")
        .select("fail_streak")
        .eq("user_id", user_id)
        .eq("params_hash", params_hash)
        .limit(1)
    )

    if not response.data:
        logger.warning(f"record_cache_fetch_failure: no cache key found for hash {params_hash[:12]}")
        return {}

    current_streak = response.data[0].get("fail_streak", 0) or 0
    new_streak = current_streak + 1
    backoff_min = calculate_backoff_minutes(new_streak)
    degraded_until = (now + timedelta(minutes=backoff_min)).isoformat()

    await sb_execute(
        sb.table("search_results_cache").update({
            "fail_streak": new_streak,
            "last_attempt_at": now.isoformat(),
            "degraded_until": degraded_until,
        }).eq("user_id", user_id).eq("params_hash", params_hash)
    )

    logger.info(
        f"Cache key {params_hash[:12]} fail_streak={new_streak}, "
        f"degraded for {backoff_min}min"
    )

    return {"fail_streak": new_streak, "degraded_until": degraded_until}


async def is_cache_key_degraded(user_id: str, params_hash: str) -> bool:
    """B-03 AC5: Check if a cache key is currently degraded."""
    from supabase_client import get_supabase, sb_execute
    sb = get_supabase()

    response = await sb_execute(
        sb.table("search_results_cache")
        .select("degraded_until")
        .eq("user_id", user_id)
        .eq("params_hash", params_hash)
        .limit(1)
    )

    if not response.data:
        return False

    degraded_until_str = response.data[0].get("degraded_until")
    if not degraded_until_str:
        return False

    try:
        degraded_until = datetime.fromisoformat(degraded_until_str.replace("Z", "+00:00"))
        if degraded_until.tzinfo is None:
            degraded_until = degraded_until.replace(tzinfo=timezone.utc)
        return degraded_until > datetime.now(timezone.utc)
    except (ValueError, TypeError):
        return False


def _process_cache_hit(data: dict, params_hash: str, level: CacheLevel) -> Optional[dict]:
    """Process raw cache data, check TTL, return structured result or None."""
    fetched_at_str = data.get("fetched_at")
    if not fetched_at_str:
        return None

    fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_hours = (now - fetched_at).total_seconds() / 3600

    if age_hours > CACHE_STALE_HOURS:
        logger.info(
            f"Cache EXPIRED at L{_level_num(level)}/{level.value} "
            f"for hash {params_hash[:12]}... "
            f"(age={age_hours:.1f}h > {CACHE_STALE_HOURS}h)"
        )
        return None

    is_stale = age_hours > CACHE_FRESH_HOURS
    status = CacheStatus.STALE if is_stale else CacheStatus.FRESH

    from middleware import search_id_var
    _search_id = search_id_var.get("-")
    logger.info(
        f"Cache HIT L{_level_num(level)}/{level.value} "
        f"[search={_search_id}] "
        f"for hash {params_hash[:12]}... "
        f"(age={age_hours:.1f}h, status={status.value})"
    )

    priority_str = data.get("priority", "cold")
    access_count = data.get("access_count", 0)
    last_accessed_str = data.get("last_accessed_at")
    last_accessed = None
    if last_accessed_str:
        try:
            last_accessed = datetime.fromisoformat(str(last_accessed_str).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass

    cache_priority = classify_priority(access_count, last_accessed)
    try:
        cache_priority = CachePriority(priority_str)
    except (ValueError, KeyError):
        pass

    result = {
        "results": data.get("results", []),
        "cached_at": fetched_at_str,
        "cached_sources": data.get("sources_json") or ["pncp"],
        "cache_age_hours": round(age_hours, 1),
        "is_stale": is_stale,
        "cache_level": level,
        "cache_status": status,
        "cache_priority": cache_priority,
    }

    coverage = data.get("coverage")
    if coverage and isinstance(coverage, dict):
        failed_ufs = coverage.get("failed_ufs", [])
        total_req = coverage.get("total_requested", 0)
        if failed_ufs and total_req > 0:
            try:
                from cron_jobs import get_pncp_cron_status
                pncp_status = get_pncp_cron_status().get("status")
                if pncp_status == "healthy" and not is_stale:
                    result["is_stale"] = True
                    result["cache_status"] = CacheStatus.STALE
            except Exception:
                pass

    return result


def _process_cache_hit_allow_expired(data: dict, params_hash: str, level: CacheLevel) -> Optional[dict]:
    """P1.3: Like _process_cache_hit but allows expired (>24h) entries as last-resort fallback."""
    fetched_at_str = data.get("fetched_at")
    if not fetched_at_str:
        return None

    fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    age_hours = (now - fetched_at).total_seconds() / 3600

    is_expired = age_hours > CACHE_STALE_HOURS
    is_stale = age_hours > CACHE_FRESH_HOURS

    from middleware import search_id_var
    _search_id = search_id_var.get("-")
    logger.info(
        f"Cache EXPIRED HIT L{_level_num(level)}/{level.value} "
        f"[search={_search_id}] "
        f"for hash {params_hash[:12]}... "
        f"(age={age_hours:.1f}h, expired={is_expired}) — allow_expired=True"
    )

    priority_str = data.get("priority", "cold")
    access_count = data.get("access_count", 0)
    last_accessed_str = data.get("last_accessed_at")
    last_accessed = None
    if last_accessed_str:
        try:
            last_accessed = datetime.fromisoformat(str(last_accessed_str).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    cache_priority = classify_priority(access_count, last_accessed)
    try:
        cache_priority = CachePriority(priority_str)
    except (ValueError, KeyError):
        pass

    return {
        "results": data.get("results", []),
        "cached_at": fetched_at_str,
        "cached_sources": data.get("sources_json") or ["pncp"],
        "cache_age_hours": round(age_hours, 1),
        "is_stale": is_stale,
        "is_expired": is_expired,
        "cache_level": level,
        "cache_status": CacheStatus.STALE if is_stale else CacheStatus.FRESH,
        "cache_priority": cache_priority,
    }


def _level_num(level: CacheLevel) -> int:
    """Map CacheLevel to numeric level for logging."""
    return {"supabase": 1, "redis": 2, "local": 3, "miss": 0}.get(level.value, 0)


# ============================================================================
# Mixpanel tracking (AC3)
# ============================================================================


def _track_cache_operation(
    operation: str,
    success: bool,
    level: CacheLevel,
    results_count: int,
    latency_ms: float,
    cache_age_seconds: float = 0,
) -> None:
    """Emit analytics event + increment counters for cache operations (B-05 AC2/AC4)."""
    try:
        from analytics_events import track_event
        track_event("cache_operation", {
            "operation": operation,
            "hit": success,
            "level": level.value,
            "cache_age_seconds": round(cache_age_seconds),
            "results_count": results_count,
            "latency_ms": round(latency_ms),
        })
    except Exception:
        pass

    try:
        from redis_pool import get_fallback_cache
        from datetime import datetime, timezone
        cache = get_fallback_cache()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if operation == "read" or operation == "get":
            if success:
                cache.incr(f"cache_counter:hits:{today}")
                if cache_age_seconds > CACHE_FRESH_HOURS * 3600:
                    cache.incr(f"cache_counter:stale_served:{today}")
                else:
                    cache.incr(f"cache_counter:fresh_served:{today}")
            else:
                cache.incr(f"cache_counter:misses:{today}")
    except Exception:
        pass


# ============================================================================
# Access tracking, reclassification, proactive refresh (B-02)
# ============================================================================


async def _increment_and_reclassify(
    user_id: str,
    params_hash: str,
    params: dict,
    result: dict,
) -> None:
    """B-02 AC4/AC5/AC9: Increment access_count, reclassify, trigger proactive refresh."""
    import json
    from supabase_client import get_supabase, sb_execute

    now = datetime.now(timezone.utc)

    try:
        sb = get_supabase()

        resp = await sb_execute(
            sb.table("search_results_cache")
            .select("access_count, last_accessed_at, priority")
            .eq("user_id", user_id)
            .eq("params_hash", params_hash)
            .limit(1)
        )

        if not resp.data:
            return

        row = resp.data[0]
        old_count = row.get("access_count", 0) or 0
        old_priority = row.get("priority", "cold")
        new_count = old_count + 1

        new_priority = classify_priority(new_count, now)

        update_data = {
            "access_count": new_count,
            "last_accessed_at": now.isoformat(),
        }

        if new_priority.value != old_priority:
            update_data["priority"] = new_priority.value
            logger.info(
                f"Cache key {params_hash[:12]} reclassified: "
                f"{old_priority} → {new_priority.value} (access_count={new_count})"
            )

        await sb_execute(
            sb.table("search_results_cache").update(update_data).eq(
                "user_id", user_id
            ).eq("params_hash", params_hash)
        )

        result["cache_priority"] = new_priority

        cache_age_hours = result.get("cache_age_hours", 0)
        if new_priority == CachePriority.HOT and cache_age_hours >= (CACHE_FRESH_HOURS - 0.5):
            try:
                # Lazy import to avoid circular dep
                from cache.swr import trigger_background_revalidation
                dispatched = await trigger_background_revalidation(
                    user_id=user_id,
                    params=params,
                    request_data=params,
                )
                if dispatched:
                    logger.info(json.dumps({
                        "event": "proactive_refresh_dispatched",
                        "params_hash": params_hash[:12],
                        "cache_age_hours": cache_age_hours,
                        "priority": new_priority.value,
                    }))
            except Exception:
                pass

    except Exception as e:
        logger.debug(f"Access tracking failed for {params_hash[:12]}: {e}")
