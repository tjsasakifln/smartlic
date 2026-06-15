"""cache/swr.py — Stale-While-Revalidate background revalidation logic.

B-01: Background revalidation after serving stale cache entries.
Uses lazy imports to avoid circular dependencies with cache.manager.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from cache.enums import compute_search_hash
from redis_resilience import safe_redis_call

logger = logging.getLogger(__name__)

# Module-level state for revalidation budget control (AC4)
_active_revalidations: int = 0
_revalidation_lock: Optional[asyncio.Lock] = None


def _get_revalidation_lock() -> asyncio.Lock:
    """Lazy init of revalidation lock (must be created inside event loop)."""
    global _revalidation_lock
    if _revalidation_lock is None:
        _revalidation_lock = asyncio.Lock()
    return _revalidation_lock


async def _is_revalidating(params_hash: str) -> bool:
    """AC3: Check if a revalidation is already in progress for this key."""
    from redis_pool import get_redis_pool, get_fallback_cache

    redis_key = f"revalidating:{params_hash}"

    redis = await get_redis_pool()
    if redis:
        return bool(await safe_redis_call(
            redis.exists(redis_key),
            fallback=False,
            method_name="exists",
            module="swr_cache",
        ))

    cache = get_fallback_cache()
    return cache.get(redis_key) is not None


async def _mark_revalidating(params_hash: str, ttl_seconds: int) -> bool:
    """AC3: Mark a key as being revalidated. Returns False if already marked."""
    from redis_pool import get_redis_pool, get_fallback_cache

    redis_key = f"revalidating:{params_hash}"

    redis = await get_redis_pool()
    if redis:
        acquired = await safe_redis_call(
            redis.set(redis_key, "1", ex=ttl_seconds, nx=True),
            fallback=None,
            method_name="set",
            module="swr_cache",
        )
        if acquired is not None:
            return bool(acquired)

    cache = get_fallback_cache()
    if cache.get(redis_key) is not None:
        return False
    cache.setex(redis_key, ttl_seconds, "1")
    return True


async def _clear_revalidating(params_hash: str) -> None:
    """Clear the revalidation dedup lock for a key."""
    from redis_pool import get_redis_pool, get_fallback_cache

    redis_key = f"revalidating:{params_hash}"

    redis = await get_redis_pool()
    if redis:
        await safe_redis_call(
            redis.delete(redis_key),
            fallback=0,
            method_name="delete",
            module="swr_cache",
        )
        return

    cache = get_fallback_cache()
    cache.delete(redis_key)


async def trigger_background_revalidation(
    user_id: str,
    params: dict,
    request_data: dict,
    search_id: Optional[str] = None,
) -> bool:
    """B-01 AC1: Dispatch background revalidation after serving stale cache."""
    global _active_revalidations
    from config import REVALIDATION_COOLDOWN_S, MAX_CONCURRENT_REVALIDATIONS

    params_hash = compute_search_hash(params)

    # AC6: Check circuit breaker before wasting resources
    try:
        from pncp_client import get_circuit_breaker
        cb = get_circuit_breaker("pncp")
        if hasattr(cb, "is_degraded") and cb.is_degraded:
            logger.info(json.dumps({
                "event": "revalidation_skipped",
                "params_hash": params_hash[:12],
                "reason": "circuit_breaker_degraded",
            }))
            return False
    except Exception:
        pass

    # AC3: Dedup — only one revalidation per key at a time
    if not await _mark_revalidating(params_hash, REVALIDATION_COOLDOWN_S):
        logger.info(json.dumps({
            "event": "revalidation_skipped",
            "params_hash": params_hash[:12],
            "reason": "already_revalidating",
        }))
        return False

    # AC4: Budget — max N concurrent revalidations per worker
    lock = _get_revalidation_lock()
    async with lock:
        if _active_revalidations >= MAX_CONCURRENT_REVALIDATIONS:
            await _clear_revalidating(params_hash)
            logger.info(json.dumps({
                "event": "revalidation_skipped",
                "params_hash": params_hash[:12],
                "reason": "budget_exceeded",
                "active": _active_revalidations,
                "max": MAX_CONCURRENT_REVALIDATIONS,
            }))
            return False
        _active_revalidations += 1

    asyncio.create_task(
        _do_revalidation(user_id, params, params_hash, request_data, search_id),
        name=f"revalidate:{params_hash[:12]}",
    )

    logger.info(json.dumps({
        "event": "revalidation_dispatched",
        "params_hash": params_hash[:12],
        "search_id": search_id,
    }))

    return True


async def _do_revalidation(
    user_id: str,
    params: dict,
    params_hash: str,
    request_data: dict,
    search_id: Optional[str],
) -> None:
    """Execute background revalidation (fire-and-forget task)."""
    global _active_revalidations
    from config import REVALIDATION_TIMEOUT

    start = time.monotonic()
    result_status = "unknown"
    new_results_count = 0
    sources_used: list = []

    try:
        async with asyncio.timeout(REVALIDATION_TIMEOUT):
            results, sources_used = await _fetch_multi_source_for_revalidation(request_data)
            new_results_count = len(results)

            if results:
                # Lazy import to avoid circular dep: cache.swr → cache.manager
                from cache.manager import save_to_cache
                duration_ms = int((time.monotonic() - start) * 1000)
                coverage = {
                    "succeeded_ufs": list(request_data["ufs"]),
                    "failed_ufs": [],
                    "total_requested": len(request_data["ufs"]),
                }
                await save_to_cache(
                    user_id=user_id,
                    params=params,
                    results=results,
                    sources=sources_used,
                    fetch_duration_ms=duration_ms,
                    coverage=coverage,
                )
                result_status = "success"

                if search_id:
                    try:
                        from progress import get_tracker
                        tracker = await get_tracker(search_id)
                        if tracker and not tracker._is_complete:
                            await tracker.emit_revalidated(
                                total_results=new_results_count,
                                fetched_at=datetime.now(timezone.utc).isoformat(),
                            )
                    except Exception:
                        pass
            else:
                result_status = "empty"

    except asyncio.TimeoutError:
        result_status = "timeout"
        try:
            from cache.manager import record_cache_fetch_failure
            await record_cache_fetch_failure(user_id, params_hash)
        except Exception:
            pass

    except Exception as e:
        result_status = "error"
        try:
            from cache.manager import record_cache_fetch_failure
            await record_cache_fetch_failure(user_id, params_hash)
        except Exception:
            pass
        logger.debug(f"Revalidation fetch failed: {e}")

    finally:
        lock = _get_revalidation_lock()
        async with lock:
            _active_revalidations = max(0, _active_revalidations - 1)

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(json.dumps({
            "event": "revalidation_complete",
            "params_hash": params_hash[:12],
            "trigger": "stale_served",
            "duration_ms": duration_ms,
            "result": result_status,
            "new_results_count": new_results_count,
            "sources": sources_used,
        }))


async def _fetch_multi_source_for_revalidation(request_data: dict) -> tuple:
    """GTM-ARCH-002 AC8/AC9: Multi-source fetch for revalidation."""

    # AC8: Try ConsolidationService (multi-source) first
    try:
        from consolidation import ConsolidationService
        from source_config.sources import get_source_config

        source_config = get_source_config()
        from source_config.sources import source_health_registry
        adapters = {}

        if source_config.pncp.enabled:
            if source_health_registry.is_available("PNCP"):
                from pncp_client import PNCPLegacyAdapter
                adapters["PNCP"] = PNCPLegacyAdapter(
                    ufs=list(request_data["ufs"]),
                    modalidades=request_data.get("modalidades"),
                )
            else:
                logger.info("[REVALIDATION] Skipping PNCP — source is DOWN in health registry")

        if source_config.compras_gov.enabled:
            if source_health_registry.is_available("COMPRAS_GOV"):
                from clients.compras_gov_client import ComprasGovAdapter
                adapters["COMPRAS_GOV"] = ComprasGovAdapter(timeout=source_config.compras_gov.timeout)
            else:
                logger.info("[REVALIDATION] Skipping COMPRAS_GOV — source is DOWN in health registry")

        if source_config.portal.enabled:
            if source_health_registry.is_available("PORTAL_COMPRAS"):
                from clients.portal_compras_client import PortalComprasAdapter
                adapters["PORTAL_COMPRAS"] = PortalComprasAdapter(
                    timeout=source_config.portal.timeout,
                )
            else:
                logger.info("[REVALIDATION] Skipping PORTAL_COMPRAS — source is DOWN in health registry")

        if adapters:
            svc = ConsolidationService(
                adapters=adapters,
                timeout_per_source=60,
                timeout_global=120,
                fail_on_all_errors=False,
            )
            try:
                consolidation_result = await svc.fetch_all(
                    data_inicial=request_data["data_inicial"],
                    data_final=request_data["data_final"],
                    ufs=set(request_data["ufs"]),
                )
                sources = [sr.source_code for sr in consolidation_result.source_results if sr.status == "success"]
                return consolidation_result.records, sources or ["consolidation"]
            finally:
                await svc.close()

    except ImportError:
        logger.debug("ConsolidationService not available, falling back to PNCP-only")
    except Exception as e:
        logger.warning(f"Multi-source revalidation failed, falling back to PNCP-only: {e}")

    # GTM-INFRA-003 AC4: Fallback — PCP+ComprasGov only (without PNCP)
    try:
        from consolidation import ConsolidationService
        from source_config.sources import get_source_config

        source_config = get_source_config()
        from source_config.sources import source_health_registry
        fallback_adapters = {}

        if source_config.compras_gov.enabled:
            if source_health_registry.is_available("COMPRAS_GOV"):
                from clients.compras_gov_client import ComprasGovAdapter
                fallback_adapters["COMPRAS_GOV"] = ComprasGovAdapter(timeout=source_config.compras_gov.timeout)
            else:
                logger.info("[REVALIDATION] Skipping COMPRAS_GOV fallback — source is DOWN")

        if source_config.portal.enabled:
            if source_health_registry.is_available("PORTAL_COMPRAS"):
                from clients.portal_compras_client import PortalComprasAdapter
                fallback_adapters["PORTAL_COMPRAS"] = PortalComprasAdapter(
                    timeout=source_config.portal.timeout,
                )
            else:
                logger.info("[REVALIDATION] Skipping PORTAL_COMPRAS fallback — source is DOWN")

        if fallback_adapters:
            logger.info(f"Revalidation fallback: trying {list(fallback_adapters.keys())} without PNCP")
            svc = ConsolidationService(
                adapters=fallback_adapters,
                timeout_per_source=60,
                timeout_global=120,
                fail_on_all_errors=False,
            )
            try:
                consolidation_result = await svc.fetch_all(
                    data_inicial=request_data["data_inicial"],
                    data_final=request_data["data_final"],
                    ufs=set(request_data["ufs"]),
                )
                sources = [sr.source_code for sr in consolidation_result.source_results if sr.status == "success"]
                if consolidation_result.records:
                    return consolidation_result.records, sources or ["fallback"]
            finally:
                await svc.close()

    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"PCP+ComprasGov fallback revalidation failed: {e}")

    # AC4 level 3: PNCP-only fallback (original behavior)
    try:
        import pncp_client as _pncp

        fetch_result = await _pncp.buscar_todas_ufs_paralelo(
            ufs=request_data["ufs"],
            data_inicial=request_data["data_inicial"],
            data_final=request_data["data_final"],
            modalidades=request_data.get("modalidades"),
        )

        if hasattr(fetch_result, "items"):
            results = fetch_result.items
        elif isinstance(fetch_result, list):
            results = fetch_result
        else:
            results = list(fetch_result)

        if results:
            return results, ["PNCP"]
    except Exception as e:
        logger.warning(f"PNCP-only fallback revalidation failed: {e}")

    return [], []
