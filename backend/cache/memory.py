"""cache/memory.py — InMemoryCache L1 layer (4h TTL, hot/warm/cold priority).

Re-exports InMemoryCache from redis_pool for the cache package API.
InMemoryCache provides LRU eviction (max 10K entries) as Redis fallback.
"""
from redis_pool import InMemoryCache, get_fallback_cache  # noqa: F401

__all__ = ["InMemoryCache", "get_fallback_cache"]
