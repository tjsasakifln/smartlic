"""cache package — Multi-level cache (L1 InMemory, L2 Supabase, L3 local file).

Entry point: cache.manager
Re-exports from cache_module (RedisCacheClient) for backward compat.
"""
from cache_module import *  # noqa: F401,F403 (RedisCacheClient backward compat)
from cache.manager import (  # noqa: F401 (re-exports)
    save_to_cache, save_to_cache_per_uf,
    get_from_cache, get_from_cache_cascade,
)
from cache.enums import CacheLevel  # noqa: F401 (re-exports), CacheStatus, CachePriority, compute_search_hash
from cache.memory import InMemoryCache  # noqa: F401 (re-exports), get_fallback_cache
