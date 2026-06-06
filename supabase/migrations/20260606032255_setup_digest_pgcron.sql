-- DIGEST-001: Schedule pg_cron jobs for email digest delivery
--
-- Creates 3 cron schedules for the three digest frequencies:
--   daily         — every day at 07:00 BRT (10:00 UTC)
--   twice_weekly  — Mon + Thu at 07:00 BRT (10:00 UTC)
--   weekly        — Mon at 07:00 BRT (10:00 UTC)
--
-- The underlying SQL functions (send_daily_digest, send_twice_weekly_digest,
-- send_weekly_digest) will be created separately — pg_cron validates the
-- schedule syntax at registration time, not the function existence. Functions
-- must exist at runtime when the cron fires.
--
-- Idempotent: unschedule + schedule pattern (existing convention in this repo).

-- ── 1. daily — every day at 07:00 BRT ──────────────────────────────────────
SELECT cron.unschedule('digest-daily')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'digest-daily');

SELECT cron.schedule(
    'digest-daily',
    '0 10 * * *',
    $$SELECT public.send_daily_digest()$$
);

-- ── 2. twice_weekly — Mon + Thu at 07:00 BRT ───────────────────────────────
SELECT cron.unschedule('digest-twice-weekly')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'digest-twice-weekly');

SELECT cron.schedule(
    'digest-twice-weekly',
    '0 10 * * 1,4',
    $$SELECT public.send_twice_weekly_digest()$$
);

-- ── 3. weekly — Mon at 07:00 BRT ───────────────────────────────────────────
SELECT cron.unschedule('digest-weekly')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'digest-weekly');

SELECT cron.schedule(
    'digest-weekly',
    '0 10 * * 1',
    $$SELECT public.send_weekly_digest()$$
);
