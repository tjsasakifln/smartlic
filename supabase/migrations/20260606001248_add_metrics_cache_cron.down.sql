-- ============================================================================
-- Migration 20260606001248 (down): Remove metrics cache refresh cron job
-- FOUNDER-002: Daily refresh of financial metrics cache
-- ============================================================================

-- 1. Unschedule the pg_cron job
SELECT cron.unschedule('metrics-cache-refresh');

-- 2. Drop the cron-trigger function
DROP FUNCTION IF EXISTS public.refresh_metrics_cache_cron;
