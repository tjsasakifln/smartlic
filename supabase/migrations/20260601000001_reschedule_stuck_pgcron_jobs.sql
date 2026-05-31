-- Fix: Reschedule 4 pg_cron jobs that have been reporting last_status=failed
-- since ~2026-04-28. Known Supabase pg_cron issue: jobs can get stuck and
-- need to be unscheduled + rescheduled to recover.
--
-- All 4 jobs use inline SQL (no parameterized functions), so the reschedule is
-- a straightforward drop + recreate. The underlying tables and indexes are
-- confirmed present (see 20260228140000, 20260225150000, 20260401000000).
--
-- Jobs rescheduled:
--   1. cleanup-reconciliation-log  — DELETE reconciliation_log > 90d
--   2. cleanup-cold-cache-entries  — DELETE search_results_cache cold > 7d
--   3. bloat-check-pncp-raw-bids   — check_pncp_raw_bids_bloat() function
--   4. retention-search-sessions   — DELETE search_sessions terminal > 180d

-- ── 1. cleanup-reconciliation-log ──────────────────────────────────────────
SELECT cron.unschedule('cleanup-reconciliation-log')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'cleanup-reconciliation-log');

SELECT cron.schedule(
    'cleanup-reconciliation-log',
    '30 4 * * *',
    $$DELETE FROM public.reconciliation_log WHERE created_at < now() - interval '90 days'$$
);

-- ── 2. cleanup-cold-cache-entries ──────────────────────────────────────────
SELECT cron.unschedule('cleanup-cold-cache-entries')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'cleanup-cold-cache-entries');

SELECT cron.schedule(
    'cleanup-cold-cache-entries',
    '0 5 * * *',
    $$
      DELETE FROM public.search_results_cache
      WHERE priority = 'cold'
        AND created_at < NOW() - INTERVAL '7 days'
    $$
);

-- ── 3. bloat-check-pncp-raw-bids ───────────────────────────────────────────
SELECT cron.unschedule('bloat-check-pncp-raw-bids')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'bloat-check-pncp-raw-bids');

SELECT cron.schedule(
    'bloat-check-pncp-raw-bids',
    '30 6 * * 0',
    $$SELECT public.check_pncp_raw_bids_bloat()$$
);

-- ── 4. retention-search-sessions ───────────────────────────────────────────
SELECT cron.unschedule('retention-search-sessions')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'retention-search-sessions');

SELECT cron.schedule(
    'retention-search-sessions',
    '20 5 * * *',
    $$DELETE FROM public.search_sessions
       WHERE status IN ('completed','failed','expired')
         AND updated_at < now() - interval '180 days'$$
);
