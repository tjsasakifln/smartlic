-- DEBT-IO-BUDGET: Replace per-INSERT trigger cleanup with pg_cron every 6h.
--
-- Problem: cleanup_search_cache_per_user() ran on EVERY INSERT into
-- search_results_cache. For each insert, it sorted all cache entries for
-- that user and deleted stale ones (OFFSET 5). On active users with many
-- searches, this wasted Disk IO on every search.
--
-- Solution: drop the trigger and schedule a pg_cron cleanup job every 6h.
-- The per-user cap of 5 entries is still enforced, but the cleanup is
-- amortized across all users in a single batch job.

-- 1. Drop the per-INSERT trigger
DROP TRIGGER IF EXISTS trg_cleanup_search_cache ON public.search_results_cache;

-- 2. Create a function for periodic cleanup (batch all users)
CREATE OR REPLACE FUNCTION public.cleanup_search_results_store()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Delete oldest entries beyond the 5 most recent for each user
    DELETE FROM public.search_results_cache
    WHERE id IN (
        SELECT id FROM (
            SELECT
                id,
                user_id,
                ROW_NUMBER() OVER (
                    PARTITION BY user_id
                    ORDER BY created_at DESC
                ) AS rn
            FROM public.search_results_cache
        ) ranked
        WHERE ranked.rn > 5
    );
END;
$$;

COMMENT ON FUNCTION public.cleanup_search_results_store() IS
    'DEBT-IO-BUDGET: Periodic batch cleanup — keeps last 5 entries per user. '
    'Scheduled via pg_cron every 6h instead of per-INSERT trigger.';

GRANT EXECUTE ON FUNCTION public.cleanup_search_results_store() TO service_role;

-- 3. Register pg_cron job (every 6 hours, starting at 01:00 UTC)
SELECT cron.schedule(
    'cleanup-search-results-store',
    '0 */6 * * *',
    $$ SELECT public.cleanup_search_results_store(); $$
);
