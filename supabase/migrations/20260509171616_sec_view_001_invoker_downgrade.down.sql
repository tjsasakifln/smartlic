-- SEC-VIEW-001 ROLLBACK: Revert the 3 views to Postgres default SECURITY DEFINER
-- behavior (security_invoker option reset).
--
-- RESET (security_invoker) returns the option to its server default (false),
-- which makes views run with the privileges of the view owner (i.e., SECURITY
-- DEFINER semantics). This is equivalent to the pre-migration state.
--
-- Use only if the downgrade caused a regression in monitoring tooling that
-- relies on bypass-of-RLS behavior. Note: backend reads via service_role do
-- NOT need this rollback, because service_role bypasses RLS regardless of
-- view security mode.

BEGIN;

ALTER VIEW public.ingestion_orphan_checkpoints RESET (security_invoker);
ALTER VIEW public.pncp_raw_bids_bloat_stats   RESET (security_invoker);
ALTER VIEW public.cron_job_health              RESET (security_invoker);

-- Restore the prior comments (drop the SEC-VIEW-001 annotation, keep the
-- original DEBT/STORY context).
COMMENT ON VIEW public.ingestion_orphan_checkpoints IS
  'DEBT-DB-NEW-002: Detects ingestion_checkpoints rows whose crawl_batch_id has no matching ingestion_runs entry. Use for periodic audit.';

COMMENT ON VIEW public.cron_job_health IS
    'STORY-1.1 — Health view aggregating cron.job + cron.job_run_details (7 day window). '
    'Consumed by get_cron_health() RPC + /v1/admin/cron-status + hourly Sentry monitor.';

COMMENT ON VIEW public.pncp_raw_bids_bloat_stats IS
    'DEBT-DB-NEW-005: Diagnostic view for pncp_raw_bids bloat monitoring. '
    'dead_row_ratio_pct > 20% → run VACUUM ANALYZE public.pncp_raw_bids. '
    'last_autovacuum NULL → autovacuum may need tuning (see bloat-monitoring.md). '
    'Usage: SELECT * FROM pncp_raw_bids_bloat_stats;';

COMMIT;
