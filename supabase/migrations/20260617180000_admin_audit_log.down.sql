-- Rollback #1974: Admin audit log migration

-- Drop pg_cron job
SELECT cron.unschedule('cleanup-admin-audit-log');

-- Drop trigger and function
DROP TRIGGER IF EXISTS trg_prevent_admin_audit_modification ON admin_audit_log;
DROP FUNCTION IF EXISTS prevent_admin_audit_modification();

-- Drop indexes
DROP INDEX IF EXISTS idx_admin_audit_log_admin_created;
DROP INDEX IF EXISTS idx_admin_audit_log_action_created;
DROP INDEX IF EXISTS idx_admin_audit_log_entity;
DROP INDEX IF EXISTS idx_admin_audit_log_created;

-- Drop table (cascades to policies)
DROP TABLE IF EXISTS admin_audit_log;
