-- Rollback: restore per-INSERT trigger and remove pg_cron job.

-- 1. Remove pg_cron job
SELECT cron.unschedule('cleanup-search-results-store');

-- 2. Drop the batch cleanup function
DROP FUNCTION IF EXISTS public.cleanup_search_results_store();

-- 3. Restore the per-INSERT trigger
CREATE OR REPLACE FUNCTION cleanup_search_cache_per_user()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM search_results_cache
    WHERE id IN (
        SELECT id FROM search_results_cache
        WHERE user_id = NEW.user_id
        ORDER BY created_at DESC
        OFFSET 5
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER trg_cleanup_search_cache
    AFTER INSERT ON search_results_cache
    FOR EACH ROW
    EXECUTE FUNCTION cleanup_search_cache_per_user();
