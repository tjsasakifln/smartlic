"""POOL-001: Universal Pool Protection — SEOSemaphore for pSEO routers.

Reusable asyncio.Semaphore wrapper with Redis negative cache, configurable
max concurrent slots, Retry-After 503 fast-fail, and Prometheus metrics.

Designed to prevent Supabase pool exhaustion under Googlebot crawl fan-out
across all 18+ programmatic SEO public routers.

Usage:
    from utils.seo_semaphore import (
        seo_semaphore, SEOSemaphore,
        SEO_SEMAPHORE_DISABLED,
    )

    _SEM = seo_semaphore("route_name", max_concurrent=3)

    @router.get("/path")
    async def handler():
        cache_key = "some:key"
        if not SEO_SEMAPHORE_DISABLED:
            await _SEM.acquire(cache_key)
        try:
            # ... query logic ...
        except (asyncio.TimeoutError, Exception):
            if not SEO_SEMAPHORE_DISABLED:
                await _SEM.set_negative_cache(cache_key)
            raise
        finally:
            if not SEO_SEMAPHORE_DISABLED:
                _SEM.release()
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global kill-switch — set env var SEO_SEMAPHORE_DISABLED=true to disable
# ALL semaphore protection across every pSEO router without code change.
# Rollback mechanism: flip env var in Railway, redeploy.
# ---------------------------------------------------------------------------
SEO_SEMAPHORE_DISABLED: bool = os.getenv("SEO_SEMAPHORE_DISABLED", "").lower() in (
    "true",
    "1",
    "yes",
)

# ---------------------------------------------------------------------------
# Prometheus metrics (graceful no-op if prometheus_client unavailable)
# ---------------------------------------------------------------------------
try:
    from metrics import _create_counter, _create_histogram

    SEO_SEMAPHORE_WAIT_SECONDS = _create_histogram(
        "smartlic_seo_semaphore_wait_seconds",
        "Time waiting for SEO semaphore slot, by route and status",
        labelnames=["route", "status"],  # status: acquired | timeout
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    )
    SEO_NEGATIVE_CACHE_HITS = _create_counter(
        "smartlic_seo_negative_cache_hits_total",
        "Number of negative cache hits per SEO route",
        labelnames=["route"],
    )
except Exception:
    # Fallback: if metrics module is not loaded yet or fails, create no-ops.
    from metrics import _NoopMetric

    SEO_SEMAPHORE_WAIT_SECONDS = _NoopMetric()
    SEO_NEGATIVE_CACHE_HITS = _NoopMetric()


class SEOSemaphore:
    """Asyncio Semaphore with Redis negative cache for SEO route pool protection.

    Each instance protects one route family. The semaphore limits concurrent
    DB-bound requests across workers. The Redis negative cache persists
    timeout/failure state across uvicorn workers so all workers respect a recent
    timeout instead of hammering Supabase simultaneously.
    """

    def __init__(
        self,
        name: str,
        max_concurrent: int = 3,
        acquire_timeout_s: float = 2.0,
        retry_after_s: int = 5,
        negative_cache_ttl_s: int = 300,
    ) -> None:
        """
        Args:
            name: Route identifier for metrics and Redis key prefix.
            max_concurrent: Max concurrent slots (default 3).
            acquire_timeout_s: Time to wait for a slot before returning 503.
            retry_after_s: Retry-After header value in seconds.
            negative_cache_ttl_s: TTL for Redis negative cache entries.
        """
        self.name = name
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._acquire_timeout_s = acquire_timeout_s
        self._retry_after_s = retry_after_s
        self._negative_cache_ttl_s = negative_cache_ttl_s
        self._redis_prefix = f"seo:negcache:{name}:"

    # ------------------------------------------------------------------
    # Negative cache (Redis + InMemory fallback)
    # ------------------------------------------------------------------

    async def check_negative_cache(self, cache_key: str) -> bool:
        """Check Redis negative cache for a recent timeout on this cache_key.

        Returns True if a negative cache entry exists — caller should serve
        stale/empty data instead of retrying the query.

        Fail-open: returns False if Redis is unavailable so we don't add latency
        to the happy path.
        """
        if not cache_key:
            return False
        try:
            from redis_pool import get_redis_pool, get_fallback_cache

            redis = await get_redis_pool()
            full_key = f"{self._redis_prefix}{cache_key}"
            if redis is not None:
                return bool(await redis.exists(full_key))
            else:
                fallback = get_fallback_cache()
                return fallback.exists(full_key)
        except Exception:
            logger.debug(
                "POOL-001: negative cache check failed for %s (non-fatal)",
                self.name,
            )
            return False

    async def set_negative_cache(self, cache_key: str) -> None:
        """Store a negative cache entry for this cache_key.

        Subsequent requests across all workers will skip the query for
        ``_negative_cache_ttl_s`` seconds, letting Googlebot's retry-storm
        cool down without re-saturating the Supabase pool.
        """
        if not cache_key:
            return
        try:
            from redis_pool import get_redis_pool, get_fallback_cache

            redis = await get_redis_pool()
            full_key = f"{self._redis_prefix}{cache_key}"
            if redis is not None:
                await redis.setex(full_key, self._negative_cache_ttl_s, "1")
            else:
                fallback = get_fallback_cache()
                fallback.setex(full_key, self._negative_cache_ttl_s, "1")
        except Exception as e:
            logger.debug(
                "POOL-001: negative cache set failed for %s (non-fatal): %s",
                self.name,
                e,
            )

    # ------------------------------------------------------------------
    # Semaphore acquire / release
    # ------------------------------------------------------------------

    async def acquire(self, cache_key: str = "") -> None:
        """Acquire the semaphore slot with a timeout.

        If the semaphore cannot be acquired within ``_acquire_timeout_s``,
        store a negative cache entry and raise HTTPException(503) with
        Retry-After header so the caller fast-fails instead of waiting in
        a queue that exhausts the Supabase pool.
        """
        if self._semaphore.locked():
            logger.warning(
                "POOL-001: %s semaphore contended (all %d slots busy, "
                "cache_key=%s) -- will wait up to %.1fs before fast-failing",
                self.name,
                self._max_concurrent,
                cache_key,
                self._acquire_timeout_s,
            )

        start_time = time.monotonic()
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self._acquire_timeout_s,
            )
            elapsed = time.monotonic() - start_time
            SEO_SEMAPHORE_WAIT_SECONDS.labels(
                route=self.name, status="acquired"
            ).observe(elapsed)
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start_time
            SEO_SEMAPHORE_WAIT_SECONDS.labels(
                route=self.name, status="timeout"
            ).observe(elapsed)
            if cache_key:
                await self.set_negative_cache(cache_key)
            logger.error(
                "POOL-001: %s semaphore exhausted (cache_key=%s, waited=%.1fs) "
                "-- returning 503",
                self.name,
                cache_key,
                elapsed,
            )
            raise HTTPException(
                status_code=503,
                detail="Servico temporariamente sobrecarregado. "
                "Tente novamente em alguns segundos.",
                headers={"Retry-After": str(self._retry_after_s)},
            )

    def release(self) -> None:
        """Release the semaphore slot."""
        self._semaphore.release()

    @asynccontextmanager
    async def protect(self, cache_key: str = "") -> AsyncIterator[None]:
        """Async context manager combining negative cache check + acquire + release.

        Usage:
            async with _SEM.protect(cache_key="some:key"):
                # query logic — if semaphore exhausted, HTTPException(503) raised
                # if negative cache hit, returns early
                pass

        Note: This does NOT handle the negative cache *set* on failure — that
        should be done in the except block of the caller since the caller knows
        *why* it failed.
        """
        need_release = False
        try:
            if cache_key:
                if await self.check_negative_cache(cache_key):
                    SEO_NEGATIVE_CACHE_HITS.labels(route=self.name).inc()
                    return
                await self.acquire(cache_key)
                need_release = True
            yield
        finally:
            if need_release:
                self.release()

    @property
    def locked(self) -> bool:
        return self._semaphore.locked()

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent


def seo_semaphore(
    name: str,
    max_concurrent: int = 3,
    acquire_timeout_s: float = 2.0,
    retry_after_s: int = 5,
    negative_cache_ttl_s: int = 300,
) -> SEOSemaphore:
    """Factory function: create a named SEOSemaphore instance.

    Usage:
        _SEM = seo_semaphore("observatorio", max_concurrent=3)
    """
    return SEOSemaphore(
        name=name,
        max_concurrent=max_concurrent,
        acquire_timeout_s=acquire_timeout_s,
        retry_after_s=retry_after_s,
        negative_cache_ttl_s=negative_cache_ttl_s,
    )
