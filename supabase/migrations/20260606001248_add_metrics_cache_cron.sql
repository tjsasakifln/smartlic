-- ============================================================================
-- Migration 20260606001248: Add metrics cache refresh cron job
-- FOUNDER-002: Daily refresh of financial metrics cache
-- Date: 2026-06-06
-- ============================================================================
--
-- This migration schedules a pg_cron job that refreshes the metrics cache
-- daily at 02:00 BRT (05:00 UTC). The cron acts as a safety net alongside
-- the lifespan background loop in ``jobs/cron/metrics_refresh.py``.
--
-- The cron calls a PostgreSQL function that triggers the backend via pg_net.
-- If pg_net is unavailable, metrics are still refreshed by the lifespan
-- background loop on the next startup / 24h cycle.
--
-- ============================================================================
-- pg_cron is already enabled by migration 022_retention_cleanup.sql.
-- ============================================================================

-- ============================================================================
-- 1. Create the cron-trigger function
-- ============================================================================
-- This function is called by pg_cron and uses pg_net to make an HTTP POST
-- request to the backend's admin metrics-cache endpoint.
-- Falls back gracefully if pg_net is not available.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.refresh_metrics_cache_cron()
RETURNS text
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  -- Attempt to trigger the backend via pg_net HTTP request.
  -- If pg_net extension is not available, this is a no-op.
  -- The actual metrics refresh runs via the lifespan background loop.
  BEGIN
    PERFORM net.http_post(
      url := 'https://api.smartlic.tech/v1/admin/refresh-metrics-cache',
      headers := jsonb_build_object(
        'Content-Type', 'application/json'
      )
    );
    RETURN 'triggered';
  EXCEPTION WHEN OTHERS THEN
    -- pg_net unavailable or request failed — metrics still refreshed
    -- by lifespan background loop. Log notice for monitoring.
    RAISE NOTICE 'pg_net HTTP request failed — metrics refresh handled by lifespan loop';
    RETURN 'fallback';
  END;
END;
$$;

COMMENT ON FUNCTION public.refresh_metrics_cache_cron IS
  'FOUNDER-002: Called by pg_cron daily at 02:00 BRT. Triggers backend metrics cache refresh via pg_net HTTP request. Falls back gracefully if pg_net is unavailable.';

-- ============================================================================
-- 2. Schedule the pg_cron job
-- ============================================================================
-- Schedule: 05:00 UTC = 02:00 BRT (Brazil daylight saving)
-- ============================================================================

SELECT cron.schedule(
    'metrics-cache-refresh',                              -- job name
    '0 5 * * *',                                          -- cron: 05:00 UTC daily
    $$SELECT public.refresh_metrics_cache_cron()$$         -- SQL to execute
);

-- ============================================================================
-- pg_cron Verification and Management
-- ============================================================================
--
-- View scheduled jobs:
--   SELECT * FROM cron.job WHERE jobname = 'metrics-cache-refresh';
--
-- View job run history:
--   SELECT * FROM cron.job_run_details
--   WHERE job_name = 'metrics-cache-refresh'
--   ORDER BY start_time DESC LIMIT 10;
--
-- Unschedule a job (if needed):
--   SELECT cron.unschedule('metrics-cache-refresh');
--
-- Manually trigger a job (for testing):
--   SELECT public.refresh_metrics_cache_cron();
--
-- ============================================================================
