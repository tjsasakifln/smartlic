"""cache/supabase.py — Supabase cache layer (L1, 24h TTL).

All supabase_client imports are lazy (inside functions) so that
patch("supabase_client.get_supabase") works in tests regardless of
which module the function lives in.

GAP-003: Every cached entry stores an ``expires_at`` timestamp set to
``created_at + CACHE_STALE_HOURS`` (24h). A pg_cron safety net cleans up
entries where ``expires_at < now()`` daily at 3h UTC.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from cache.enums import CACHE_STALE_HOURS, compute_global_hash

logger = logging.getLogger(__name__)


async def _save_to_supabase(
    user_id: str, params_hash: str, params: dict, results: list, sources: list,
    *, fetch_duration_ms: Optional[int] = None, coverage: Optional[dict] = None,
) -> None:
    """Save to Supabase cache (Level 1)."""
    from supabase_client import get_supabase, sb_execute
    sb = get_supabase()

    now_utc = datetime.now(timezone.utc)
    now = now_utc.isoformat()
    row = {
        "user_id": user_id,
        "params_hash": params_hash,
        "params_hash_global": compute_global_hash(params),
        "search_params": params,
        "results": results,
        "total_results": len(results),
        "sources_json": sources,
        "fetched_at": now,
        "created_at": now,
        "last_success_at": now,
        "last_attempt_at": now,
        "fail_streak": 0,
        "degraded_until": None,
        # GAP-003: expires_at = created_at + CACHE_STALE_HOURS (24h)
        # Used by pg_cron safety net to clean stale entries.
        "expires_at": (now_utc + timedelta(hours=CACHE_STALE_HOURS)).isoformat(),
    }
    if coverage is not None:
        row["coverage"] = coverage
    if fetch_duration_ms is not None:
        row["fetch_duration_ms"] = fetch_duration_ms

    # STORY-265 AC2: Application-level JSONB size guard (2 MB limit)
    JSONB_MAX_BYTES = 2_097_152
    results_size = len(json.dumps(results).encode("utf-8"))
    if results_size > JSONB_MAX_BYTES:
        original_count = len(results)
        while results and len(json.dumps(results).encode("utf-8")) > JSONB_MAX_BYTES:
            results = results[: len(results) * 3 // 4]
        row["results"] = results
        row["total_results"] = len(results)
        logger.warning(
            "STORY-265: results JSONB truncated",
            extra={
                "original_count": original_count,
                "truncated_count": len(results),
                "original_bytes": results_size,
                "user_id": user_id,
                "params_hash": params_hash[:12],
            },
        )

    try:
        from models.cache import SearchResultsCacheRow
        expected = SearchResultsCacheRow.expected_columns()
        unknown_keys = set(row.keys()) - expected
        if unknown_keys:
            logger.warning(f"CRIT-001: _save_to_supabase payload has unknown keys: {sorted(unknown_keys)}")
    except ImportError:
        pass

    _max_retries = 1
    for _attempt in range(_max_retries + 1):
        try:
            await sb_execute(
                sb.table("search_results_cache").upsert(
                    row, on_conflict="user_id,params_hash"
                )
            )
            return
        except Exception as _upsert_err:
            _err_type = type(_upsert_err).__name__
            _err_msg = str(_upsert_err)[:300]
            if _attempt < _max_retries:
                logger.warning(
                    f"PHASE-0: _save_to_supabase attempt {_attempt + 1} failed "
                    f"({_err_type}: {_err_msg}), retrying in 1s..."
                )
                await asyncio.sleep(1)
            else:
                logger.error(
                    f"PHASE-0: _save_to_supabase FAILED after {_max_retries + 1} attempts — "
                    f"{_err_type}: {_err_msg} "
                    f"(user_id={user_id[:8]}, hash={params_hash[:12]}, "
                    f"n_results={len(results)}, row_keys={sorted(row.keys())})"
                )
                raise


async def _get_from_supabase(user_id: str, params_hash: str) -> Optional[dict]:
    """Read from Supabase cache (Level 1)."""
    from supabase_client import get_supabase, sb_execute
    sb = get_supabase()

    response = await sb_execute(
        sb.table("search_results_cache")
        .select("results, total_results, sources_json, fetched_at, created_at, priority, access_count, last_accessed_at")
        .eq("user_id", user_id)
        .eq("params_hash", params_hash)
        .order("created_at", desc=True)
        .limit(1)
    )

    if not response.data:
        return None

    row = response.data[0]

    try:
        expected_fields = {"results", "total_results", "sources_json", "fetched_at", "priority", "access_count", "last_accessed_at"}
        missing_fields = expected_fields - set(row.keys())
        if missing_fields:
            logger.warning(f"CRIT-001: _get_from_supabase row missing fields: {sorted(missing_fields)}")
    except ImportError:
        pass

    fetched_at_str = row.get("fetched_at") or row.get("created_at")
    return {
        "results": row.get("results", []),
        "total_results": row.get("total_results", 0),
        "sources_json": row.get("sources_json"),
        "fetched_at": fetched_at_str,
        "priority": row.get("priority", "cold"),
        "access_count": row.get("access_count", 0),
        "last_accessed_at": row.get("last_accessed_at"),
    }


async def _get_global_fallback_from_supabase(params: dict) -> Optional[dict]:
    """GTM-ARCH-002 AC1/AC4: Cross-user global cache fallback."""
    from supabase_client import get_supabase, sb_execute
    sb = get_supabase()

    global_hash = compute_global_hash(params)

    response = await sb_execute(
        sb.table("search_results_cache")
        .select("results, total_results, sources_json, fetched_at, created_at, priority, access_count, last_accessed_at")
        .eq("params_hash_global", global_hash)
        .order("created_at", desc=True)
        .limit(1)
    )

    if not response.data:
        return None

    row = response.data[0]
    fetched_at_str = row.get("fetched_at") or row.get("created_at")
    return {
        "results": row.get("results", []),
        "total_results": row.get("total_results", 0),
        "sources_json": row.get("sources_json"),
        "fetched_at": fetched_at_str,
        "priority": row.get("priority", "cold"),
        "access_count": row.get("access_count", 0),
        "last_accessed_at": row.get("last_accessed_at"),
    }
