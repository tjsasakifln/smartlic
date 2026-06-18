-- ADMIN-AUDIT (#1974): Immutable audit log for administrative actions.
--
-- Creates the admin_audit_log table to record every admin mutation with
-- an immutable INSERT-only trail. Required for LGPD compliance audit
-- requirements (Art. 37 — accountability).
--
-- RLS: INSERT only via service_role (backend), SELECT only for
-- admin:super and admin:compliance roles. No UPDATE/DELETE policies
-- exist — the table is INSERT-only by design.
--
-- Cleanup: pg_cron job deletes entries older than 365 days daily at 8h UTC.

-- ============================================================================
-- 1. Create table
-- ============================================================================

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    admin_id UUID NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    ip INET,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================================
-- 2. Indexes for common query patterns
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_admin_audit_admin_id ON admin_audit_log (admin_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_entity_type ON admin_audit_log (entity_type);
CREATE INDEX IF NOT EXISTS idx_admin_audit_action ON admin_audit_log (action);
CREATE INDEX IF NOT EXISTS idx_admin_audit_created_at ON admin_audit_log (created_at DESC);

-- Composite index for the most common filter pattern: admin_id + time range
CREATE INDEX IF NOT EXISTS idx_admin_audit_admin_time ON admin_audit_log (admin_id, created_at DESC);

-- ============================================================================
-- 3. RLS — immutable INSERT-only table
-- ============================================================================

ALTER TABLE admin_audit_log ENABLE ROW LEVEL SECURITY;

-- Policy: SELECT only for compliance and super admins
-- The has_admin_role function checks if the user's admin_roles contains
-- the specified role (admin:compliance). admin:super has full access.
CREATE POLICY "admin_audit_log_select_compliance" ON admin_audit_log
    FOR SELECT
    USING (
        auth.role() = 'service_role'
        OR has_admin_role(
            COALESCE(
                (SELECT admin_roles FROM profiles WHERE id = auth.uid()),
                ARRAY[]::text[]
            ),
            'admin:compliance'
        )
    );

-- Policy: INSERT allowed for service_role only (backend writes via service_role key)
CREATE POLICY "admin_audit_log_insert_service" ON admin_audit_log
    FOR INSERT
    WITH CHECK (auth.role() = 'service_role');

-- NO UPDATE/DELETE policies — this enforces immutability.
-- Entries cannot be modified or deleted; cleanup is handled by pg_cron
-- retention job that runs as service_role.

-- ============================================================================
-- 4. pg_cron: daily retention cleanup (365 days)
-- ============================================================================

-- Idempotent: unschedule if already exists, then re-schedule
SELECT cron.unschedule('cleanup-admin-audit-log')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'cleanup-admin-audit-log');

SELECT cron.schedule(
    'cleanup-admin-audit-log',
    '0 8 * * *',   -- Daily at 08:00 UTC
    $$DELETE FROM admin_audit_log WHERE created_at < NOW() - INTERVAL '365 days'$$
);

-- ============================================================================
-- 5. Log migration execution for audit trail
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE 'ADMIN-AUDIT (#1974): admin_audit_log table created with 365d retention';
END $$;
