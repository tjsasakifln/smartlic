"""cache package — Multi-level cache (L1 InMemory, L2 Supabase, L3 local file).

Entry point: cache.manager
"""
from cache.manager import (  # noqa: F401
    save_to_cache, save_to_cache_per_uf,
    get_from_cache, get_from_cache_cascade,
)
from cache.enums import (  # noqa: F401
    CacheLevel, CacheStatus, CachePriority, compute_search_hash,
)
from redis_pool import InMemoryCache, get_fallback_cache  # noqa: F401
from cache_module import redis_cache  # noqa: F401
