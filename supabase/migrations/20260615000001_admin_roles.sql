-- Migration: Admin roles table for granular RBAC (#1778)
-- Replaces boolean is_admin with role-based access control.
-- Supports DASHBOARD, USER_MANAGER, BILLING, DATA_ACCESS, MASTER roles.

CREATE TABLE IF NOT EXISTS admin_roles (
  user_id UUID PRIMARY KEY REFERENCES profiles(id) ON DELETE CASCADE,
  roles TEXT[] NOT NULL DEFAULT '{}',
  granted_by UUID REFERENCES profiles(id),
  granted_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: service_role only (no user access to this table)
ALTER TABLE admin_roles ENABLE ROW LEVEL SECURITY;

CREATE POLICY admin_roles_service_only ON admin_roles
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- Revoke all from anon and authenticated roles
REVOKE ALL ON admin_roles FROM anon, authenticated;
GRANT ALL ON admin_roles TO service_role;

-- Index for fast role lookup
CREATE INDEX IF NOT EXISTS idx_admin_roles_user_id ON admin_roles(user_id);

COMMENT ON TABLE admin_roles IS 'Granular admin role assignments (#1778). Roles: dashboard, user_manager, billing, data_access, master. service_role only.';
COMMENT ON COLUMN admin_roles.roles IS 'Array of role strings, e.g. {dashboard,user_manager}';
COMMENT ON COLUMN admin_roles.granted_by IS 'User ID of the admin who granted these roles';
COMMENT ON COLUMN admin_roles.granted_at IS 'Timestamp when roles were granted';
