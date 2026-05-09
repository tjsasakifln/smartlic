-- SEC-VIEW-001: Downgrade 3 SECURITY DEFINER views to SECURITY INVOKER
-- Issue: #950 — Supabase advisor lint flagged 3 views in `public` schema
-- running with SECURITY DEFINER semantics, which bypass RLS of the querying
-- role. The views are internal monitoring/debug surfaces consumed only by the
-- backend via `service_role`, so downgrading to invoker mode is the correct
-- least-privilege posture: `service_role` retains access (bypasses RLS by
-- design), while `authenticated`/`anon` get a deterministic permission_denied.
--
-- Refs:
--   - feedback_secdef_search_path_trap (related vuln family — SECDEF surface)
--   - Supabase docs: https://supabase.com/docs/guides/database/postgres/row-level-security#security-definer-vs-security-invoker-views
--   - Postgres 15 release notes: ALTER VIEW SET (security_invoker = true)
--
-- Postgres 15+ syntax. Supabase Postgres 17 confirmed compatible.
-- Idempotent: ALTER VIEW SET is safe to re-apply.

BEGIN;

ALTER VIEW public.ingestion_orphan_checkpoints SET (security_invoker = true);
ALTER VIEW public.pncp_raw_bids_bloat_stats   SET (security_invoker = true);
ALTER VIEW public.cron_job_health              SET (security_invoker = true);

COMMENT ON VIEW public.ingestion_orphan_checkpoints IS
  'DEBT-DB-NEW-002 / SEC-VIEW-001: Detects ingestion_checkpoints rows whose crawl_batch_id has no matching ingestion_runs entry. Use for periodic audit. Runs in SECURITY INVOKER mode — querying role must have SELECT on underlying tables (service_role in production).';

COMMENT ON VIEW public.pncp_raw_bids_bloat_stats IS
  'DEBT-203 / SEC-VIEW-001: Diagnostic bloat stats for pncp_raw_bids. Runs in SECURITY INVOKER mode — querying role must have SELECT on pg_catalog system relations (default for all roles) and on the underlying table.';

COMMENT ON VIEW public.cron_job_health IS
  'STORY-1.1 / SEC-VIEW-001: pg_cron job health snapshot (last 7 days). Runs in SECURITY INVOKER mode — querying role must have SELECT on cron.job and cron.job_run_details (granted to service_role in Supabase by default). Programmatic access should use the get_cron_health() RPC, which retains SECURITY DEFINER for backend admin endpoints.';

COMMIT;

-- ════════════════════════════════════════════════════════════════════════
-- AC3 smoke test SQL (run manually as each role in staging post-deploy):
-- ════════════════════════════════════════════════════════════════════════
--
-- SET ROLE authenticated;
--   SELECT * FROM public.ingestion_orphan_checkpoints LIMIT 1;  -- expect: permission denied
--   SELECT * FROM public.pncp_raw_bids_bloat_stats LIMIT 1;     -- expect: permission denied
--   SELECT * FROM public.cron_job_health LIMIT 1;               -- expect: permission denied
-- RESET ROLE;
--
-- SET ROLE anon;
--   SELECT * FROM public.ingestion_orphan_checkpoints LIMIT 1;  -- expect: permission denied
-- RESET ROLE;
--
-- SET ROLE service_role;
--   SELECT * FROM public.ingestion_orphan_checkpoints LIMIT 1;  -- expect: rows or empty (success)
--   SELECT * FROM public.pncp_raw_bids_bloat_stats LIMIT 1;     -- expect: rows or empty (success)
--   SELECT * FROM public.cron_job_health LIMIT 1;               -- expect: rows or empty (success)
-- RESET ROLE;
--
-- ════════════════════════════════════════════════════════════════════════
-- AC4 advisor re-run instructions (post-deploy):
-- ════════════════════════════════════════════════════════════════════════
--   1. After CI auto-applies this migration, open Supabase Dashboard →
--      Database → Advisor and run the security lint.
--   2. Confirm zero matches for the rule "Security Definer View" against
--      the three view names above.
--   3. Attach the resulting JSON or screenshot to PR #<n> as evidence.
-- ════════════════════════════════════════════════════════════════════════
