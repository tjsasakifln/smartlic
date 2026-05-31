-- Revert: The forward migration just reschedules existing jobs — the down
-- migration is a no-op since dropping and recreating is idempotent. We keep
-- the jobs running; reverting would leave them unscheduled, which is worse.
-- If you truly need to revert, manually unschedule the jobs:
--   SELECT cron.unschedule('cleanup-reconciliation-log');
--   SELECT cron.unschedule('cleanup-cold-cache-entries');
--   SELECT cron.unschedule('bloat-check-pncp-raw-bids');
--   SELECT cron.unschedule('retention-search-sessions');
SELECT 1;
