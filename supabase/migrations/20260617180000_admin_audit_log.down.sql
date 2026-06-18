-- ADMIN-AUDIT (#1974): Rollback — remove admin_audit_log table and cron job.
--
-- Removes the table, its indexes, the cron schedule, and any RLS policies.

-- 1. Remove pg_cron schedule
SELECT cron.unschedule('cleanup-admin-audit-log')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'cleanup-admin-audit-log');

-- 2. Drop RLS policies (if they exist)
DROP POLICY IF EXISTS "admin_audit_log_select_compliance" ON admin_audit_log;
DROP POLICY IF EXISTS "admin_audit_log_insert_service" ON admin_audit_log;

-- 3. Drop indexes (if they exist)
DROP INDEX IF EXISTS idx_admin_audit_admin_id;
DROP INDEX IF EXISTS idx_admin_audit_entity_type;
DROP INDEX IF EXISTS idx_admin_audit_action;
DROP INDEX IF EXISTS idx_admin_audit_created_at;
DROP INDEX IF EXISTS idx_admin_audit_admin_time;

-- 4. Drop table
DROP TABLE IF EXISTS admin_audit_log;

-- 5. Log rollback
DO $$
BEGIN
    RAISE NOTICE 'ADMIN-AUDIT (#1974): admin_audit_log table removed';
END $$;
