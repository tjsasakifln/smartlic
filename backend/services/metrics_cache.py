"""Metrics cache service — compute financial metrics and cache in Redis.

FOUNDER-002: Redis cache for revenue/financial metrics with 1h TTL.
Cache-first with graceful degradation (recompute on miss).

Usage:
    from services.metrics_cache import get_cached_metrics, invalidate_metrics_cache

    metrics = await get_cached_metrics()
    # => {"mrr_current": ..., "churn_rate_30d": ..., ...}

    await invalidate_metrics_cache()
    # => clears all metrics:revenue:* keys
"""

import json
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

METRICS_TTL = 3600  # 1 hour
METRICS_PREFIX = "metrics:revenue"

METRICS = [
    "mrr_current",
    "churn_rate_30d",
    "trial_to_paid_30d",
    "trial_to_paid_90d",
    "d7_retention",
    "arpa",
]


async def compute_all_metrics() -> dict:
    """Compute all financial metrics from SQL functions.

    Calls Supabase RPCs for each metric and assembles a single dict.
    Graceful degradation: returns 0 / empty values on error.
    """
    from supabase_client import get_supabase, sb_execute

    sb = get_supabase()
    end_date = date.today()
    start_date = end_date - timedelta(days=365)

    results = {}

    # MRR (current month — last entry in the time series)
    try:
        mrr_data = await sb_execute(
            sb.rpc("get_mrr", {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            }),
            category="rpc",
        )
        data = mrr_data.data or []
        results["mrr_current"] = data[-1] if data else {
            "month": end_date.isoformat(), "mrr": 0, "subscriber_count": 0
        }
    except Exception as exc:
        logger.warning("Failed to compute MRR: %s", exc)
        results["mrr_current"] = {
            "month": end_date.isoformat(), "mrr": 0, "subscriber_count": 0
        }

    # Churn rate (30d)
    try:
        churn = await sb_execute(sb.rpc("get_churn_rate_30d"), category="rpc")
        results["churn_rate_30d"] = float(churn.data) if churn.data else 0.0
    except Exception as exc:
        logger.warning("Failed to compute churn rate: %s", exc)
        results["churn_rate_30d"] = 0.0

    # Trial to paid (30d)
    try:
        ttp30 = await sb_execute(sb.rpc("get_trial_to_paid_30d"), category="rpc")
        results["trial_to_paid_30d"] = float(ttp30.data) if ttp30.data else 0.0
    except Exception as exc:
        logger.warning("Failed to compute trial_to_paid_30d: %s", exc)
        results["trial_to_paid_30d"] = 0.0

    # Trial to paid (90d)
    try:
        ttp90 = await sb_execute(sb.rpc("get_trial_to_paid_90d"), category="rpc")
        results["trial_to_paid_90d"] = float(ttp90.data) if ttp90.data else 0.0
    except Exception as exc:
        logger.warning("Failed to compute trial_to_paid_90d: %s", exc)
        results["trial_to_paid_90d"] = 0.0

    # D7 retention
    try:
        d7 = await sb_execute(sb.rpc("get_d7_retention"), category="rpc")
        results["d7_retention"] = float(d7.data) if d7.data else 0.0
    except Exception as exc:
        logger.warning("Failed to compute D7 retention: %s", exc)
        results["d7_retention"] = 0.0

    # ARPA
    try:
        arpa = await sb_execute(sb.rpc("get_arpa"), category="rpc")
        results["arpa"] = float(arpa.data) if arpa.data else 0.0
    except Exception as exc:
        logger.warning("Failed to compute ARPA: %s", exc)
        results["arpa"] = 0.0

    logger.info(
        "Computed all metrics: mrr=%.2f churn=%.2f%% ttp30=%.2f%% d7=%.2f%% arpa=%.2f",
        results.get("mrr_current", {}).get("mrr", 0),
        results.get("churn_rate_30d", 0),
        results.get("trial_to_paid_30d", 0),
        results.get("d7_retention", 0),
        results.get("arpa", 0),
    )
    return results


async def cache_metrics(metrics: dict) -> None:
    """Store metrics in Redis with TTL.

    Each metric is serialised to JSON and stored under ``metrics:revenue:{name}``.
    Uses a Redis pipeline for atomic batch write.
    Falls back gracefully if Redis is unavailable.
    """
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            logger.warning(
                "Redis unavailable — metrics not cached (InMemoryCache will serve)"
            )
            return

        pipe = redis.pipeline()
        for key, value in metrics.items():
            pipe.setex(
                f"{METRICS_PREFIX}:{key}", METRICS_TTL, json.dumps(value, default=str)
            )
        await pipe.execute()
        logger.info("Cached %d metrics to Redis (TTL=%ds)", len(metrics), METRICS_TTL)
    except Exception as exc:
        logger.warning("Failed to cache metrics: %s", exc)


async def get_cached_metrics() -> dict:
    """Get all metrics from cache, recomputing on cache miss.

    Cache-first strategy: reads each metric key from Redis.
    If any key is missing, recomputes ALL metrics and re-caches.
    Returns the full dict in both cases.
    """
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
    except Exception:
        redis = None

    if redis:
        results = {}
        needs_compute = False

        for metric in METRICS:
            try:
                cached = await redis.get(f"{METRICS_PREFIX}:{metric}")
                if cached:
                    results[metric] = json.loads(cached)
                else:
                    needs_compute = True
            except Exception as exc:
                logger.debug("Cache read failed for %s: %s", metric, exc)
                needs_compute = True

        if not needs_compute:
            return results

        logger.info("Cache miss for some metrics, recomputing all")
        computed = await compute_all_metrics()
        await cache_metrics(computed)
        return computed

    # Redis unavailable — compute directly (graceful degradation)
    logger.info("Redis unavailable, computing metrics directly")
    return await compute_all_metrics()


async def invalidate_metrics_cache() -> int:
    """Delete all metrics cache keys from Redis.

    Returns:
        Number of deleted keys.
    """
    try:
        from redis_pool import get_redis_pool

        redis = await get_redis_pool()
        if redis is None:
            logger.warning("Redis unavailable — cannot invalidate metrics cache")
            return 0
        keys = await redis.keys(f"{METRICS_PREFIX}:*")
        if keys:
            await redis.delete(*keys)
        logger.info("Invalidated %d metrics cache keys", len(keys))
        return len(keys)
    except Exception as exc:
        logger.warning("Failed to invalidate metrics cache: %s", exc)
        return 0
