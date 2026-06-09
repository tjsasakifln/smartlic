-- ============================================================================
-- DOWN: cleanup_orphan_checkpoints — drops the function
-- Reverses 20260608212731_cleanup_orphan_checkpoints.sql
-- Date: 2026-06-08
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Drops the cleanup_orphan_checkpoints() function created in the
--   up migration. The companion pg_cron job must be unscheduled
--   separately via the down migration of the schedule file.
-- ============================================================================

DROP FUNCTION IF EXISTS public.cleanup_orphan_checkpoints();
