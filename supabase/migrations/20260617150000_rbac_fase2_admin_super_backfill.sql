-- RBAC-FASE2 (#1954): Backfill admin_roles for legacy boolean admins.
--
-- Migrates users with is_admin=true AND admin_roles IS NULL to the new
-- granular role system by setting admin_roles = ARRAY['admin:super'].
-- The 'admin:super' role grants access to ALL granular endpoints,
-- preserving existing admin access levels without breaking changes.

UPDATE profiles
SET admin_roles = ARRAY['admin:super']
WHERE is_admin = true
  AND (admin_roles IS NULL OR admin_roles = ARRAY[]::text[] OR admin_roles = '{}');

-- Log count for audit trail
DO $$
DECLARE
  affected INT;
BEGIN
  GET DIAGNOSTICS affected = ROW_COUNT;
  RAISE NOTICE 'RBAC-FASE2: % profiles backfilled with admin:super', affected;
END $$;
