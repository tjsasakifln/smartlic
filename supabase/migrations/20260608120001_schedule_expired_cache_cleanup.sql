-- GAP-003: pg_cron safety net — daily cleanup of expired cache entries.
--
-- Deletes rows from search_results_cache where expires_at < now().
-- Runs daily at 3h UTC (off-peak, staggered from other cleanup jobs).
--
-- This is a safety net: the primary cache expiry mechanism is the
-- application-level read-time check in backend/cache/_ops.py
-- (_process_cache_hit discards entries > CACHE_STALE_HOURS).
--
-- The pg_cron job prevents database bloat from stale entries that escape
-- the read-time check (e.g., entries written by a worker before the
-- migration was applied, where expires_at is still NULL).
--
-- Why 3h UTC? (00:00 BRT / 01:00 BRST)
--   - Staggered from created_at-based cleanup at 4h UTC (20260414120200)
--   - Separate window from purge-old-bids at 7h UTC (STORY-1.2)
--   - Separate window from search_results_store cleanup at 4h UTC
--   - Off-peak hours for Brazilian users (active hours 10h-18h BRT)

-- Ensure pg_cron extension exists (safe to call multiple times)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Idempotent: unschedule existing job before re-creating
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'cleanup-expired-cache') THEN
        PERFORM cron.unschedule('cleanup-expired-cache');
    END IF;
END $$;

SELECT cron.schedule(
    'cleanup-expired-cache',
    '0 3 * * *',  -- Daily at 3:00 UTC
    $$DELETE FROM public.search_results_cache WHERE expires_at < now()$$
);

COMMENT ON FUNCTION public.cleanup_search_results_store() IS NULL;  -- no-op, just for syntax
