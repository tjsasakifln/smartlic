-- Rollback GAP-003: Remove pg_cron safety net for expired cache cleanup.
--
-- After rollback, expired cache entries will only be cleaned up by the
-- existing created_at-based job (20260414120200_schedule_search_cache_cleanup)
-- which deletes entries older than 24h based on created_at.
-- The expires_at column and index remain.

-- Remove the pg_cron job
SELECT cron.unschedule('cleanup-expired-cache');
