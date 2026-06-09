-- ============================================================================
-- DOWN: cleanup_orphan_checkpoints_schedule — unschedules the pg_cron job
-- Reverses 20260608212732_cleanup_orphan_checkpoints_schedule.sql
-- Date: 2026-06-08
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Unschedules the 'cleanup-orphan-checkpoints' pg_cron job. The
--   underlying function cleanup_orphan_checkpoints() is NOT dropped
--   here (it is removed by the down migration of the function file).
-- ============================================================================

SELECT cron.unschedule('cleanup-orphan-checkpoints')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'cleanup-orphan-checkpoints');
