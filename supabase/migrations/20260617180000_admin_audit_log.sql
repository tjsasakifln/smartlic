-- #1974: Admin audit log — immutable trail for all administrative actions
-- LGPD/compliance requirement: every admin action must have an auditable trail.

-- ============================================================================
-- 1. admin_audit_log — immutable audit trail table
-- ============================================================================

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_id UUID NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    details JSONB DEFAULT '{}'::jsonb,
    ip INET,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_admin_audit_log_admin_created
    ON admin_audit_log(admin_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action_created
    ON admin_audit_log(action, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_entity
    ON admin_audit_log(entity_type, entity_id);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created
    ON admin_audit_log(created_at DESC);

-- ============================================================================
-- 2. Row-Level Security (RLS)
-- ============================================================================
-- Only admin:super and admin:compliance can SELECT.
-- INSERT/UPDATE/DELETE are blocked at RLS level (write happens via backend
-- service_role, which bypasses RLS).

ALTER TABLE admin_audit_log ENABLE ROW LEVEL SECURITY;

-- Read-only for compliance/super admins (uses existing has_admin_role function)
CREATE POLICY "Admin audit log read-only for compliance"
    ON admin_audit_log FOR SELECT
    USING (has_admin_role('admin:super') OR has_admin_role('admin:compliance'));

-- Block direct INSERT (backend uses service_role which bypasses RLS)
CREATE POLICY "Block direct insert"
    ON admin_audit_log FOR INSERT
    WITH CHECK (false);

-- Block direct UPDATE
CREATE POLICY "Block direct update"
    ON admin_audit_log FOR UPDATE
    USING (false);

-- Block direct DELETE
CREATE POLICY "Block direct delete"
    ON admin_audit_log FOR DELETE
    USING (false);

-- ============================================================================
-- 3. Immutability trigger — prevents UPDATE/DELETE at database level
-- ============================================================================

CREATE OR REPLACE FUNCTION prevent_admin_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'admin_audit_log is immutable: UPDATE and DELETE are not allowed (PG code: P0001)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_prevent_admin_audit_modification
    BEFORE UPDATE OR DELETE ON admin_audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_admin_audit_modification();

-- ============================================================================
-- 4. pg_cron cleanup job — 365-day retention (#1974 AC5)
-- ============================================================================

SELECT cron.schedule(
    'cleanup-admin-audit-log',
    '0 3 * * *',
    $$DELETE FROM admin_audit_log WHERE created_at < now() - interval '365 days'$$
);

-- ============================================================================
-- 5. Comments
-- ============================================================================

COMMENT ON TABLE admin_audit_log IS '#1974: Immutable audit trail for all admin actions. SELECT only for admin:super and admin:compliance.';
COMMENT ON COLUMN admin_audit_log.admin_id IS 'UUID of the admin who performed the action';
COMMENT ON COLUMN admin_audit_log.action IS 'Action identifier (e.g. assign_plan, create_user, invalidate_cache)';
COMMENT ON COLUMN admin_audit_log.entity_type IS 'Type of affected entity (e.g. user, cache, feature_flag, reconciliation)';
COMMENT ON COLUMN admin_audit_log.entity_id IS 'ID of the affected entity';
COMMENT ON COLUMN admin_audit_log.details IS 'Action metadata (PII sanitized before logging via log_sanitizer.sanitize_dict)';
COMMENT ON COLUMN admin_audit_log.ip IS 'Client IP address of the admin';
COMMENT ON COLUMN admin_audit_log.created_at IS 'When the action was performed';
COMMENT ON FUNCTION prevent_admin_audit_modification IS '#1974: Trigger function that raises exception on UPDATE/DELETE to enforce immutability';
COMMENT ON TRIGGER trg_prevent_admin_audit_modification ON admin_audit_log IS '#1974: Fires before UPDATE/DELETE, raises exception to enforce immutability';
