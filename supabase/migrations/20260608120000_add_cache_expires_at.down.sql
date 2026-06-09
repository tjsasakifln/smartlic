-- Rollback GAP-003: Remove expires_at column and index.
--
-- After rollback, stale cache cleanup falls back to the existing
-- created_at-based pg_cron job (see 20260414120200_schedule_search_cache_cleanup)
-- and the application-level read-time expiry check in _process_cache_hit.

DROP INDEX IF EXISTS idx_search_results_cache_expires_at;

ALTER TABLE public.search_results_cache
    DROP COLUMN IF EXISTS expires_at;
