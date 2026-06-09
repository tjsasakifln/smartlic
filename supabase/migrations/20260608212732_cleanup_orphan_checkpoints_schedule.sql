-- GAP-007: Schedule weekly orphan checkpoint cleanup via pg_cron
--
-- Runs every Sunday at 8:00 UTC (5:00 BRT) to remove checkpoint
-- records from ingestion_checkpoints whose UF is not in the active
-- 27-UF list.
--
-- Depends on function public.cleanup_orphan_checkpoints() defined in
-- 20260608212731_cleanup_orphan_checkpoints.sql.
--
-- ============================================================================
-- Idempotent: unschedule + schedule pattern to avoid duplicate job errors.
-- ============================================================================

SELECT cron.unschedule('cleanup-orphan-checkpoints')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'cleanup-orphan-checkpoints');

SELECT cron.schedule(
    'cleanup-orphan-checkpoints',
    '0 8 * * 0',   -- Sunday 08:00 UTC
    $$SELECT public.cleanup_orphan_checkpoints()$$
);
