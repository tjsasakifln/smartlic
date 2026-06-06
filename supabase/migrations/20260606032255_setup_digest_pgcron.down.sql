-- DIGEST-001: Rollback — unschedule all digest cron jobs.

SELECT cron.unschedule('digest-daily')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'digest-daily');

SELECT cron.unschedule('digest-twice-weekly')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'digest-twice-weekly');

SELECT cron.unschedule('digest-weekly')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'digest-weekly');
