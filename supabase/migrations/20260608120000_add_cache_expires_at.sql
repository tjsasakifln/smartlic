-- GAP-003: Add expires_at column to search_results_cache for TTL-based cleanup.
--
-- Every cache entry now stores an explicit expiry timestamp, computed at
-- write time as created_at + CACHE_STALE_HOURS (24h). A pg_cron safety net
-- (see sibling migration 20260608120001) deletes expired rows daily.
--
-- This replaces the implicit read-time expiry check (backend/cache/_ops.py
-- _process_cache_hit compares fetched_at against CACHE_STALE_HOURS) with
-- a database-level column that enables deterministic cleanup.

-- 1. Add expires_at column (nullable for backward compat with existing rows)
ALTER TABLE public.search_results_cache
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;

COMMENT ON COLUMN public.search_results_cache.expires_at IS
    'GAP-003: Cache entry expiry timestamp. Set to created_at + CACHE_STALE_HOURS (24h) at write time. '
    'pg_cron safety net cleans up WHERE expires_at < now() daily at 3h UTC. '
    'Null for rows written before migration — treated as expired by application code.';

-- 2. Index for efficient cleanup queries
CREATE INDEX IF NOT EXISTS idx_search_results_cache_expires_at
    ON public.search_results_cache(expires_at);
