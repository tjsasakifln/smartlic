-- RBAC-FASE2 (#1954): Rollback — revert admin_roles to NULL for backfilled rows.
--
-- Only reverts rows that have EXACTLY admin:super as their only role and
-- still have is_admin=true. Users who were granted additional granular roles
-- via the admin dashboard are NOT affected by this rollback.

UPDATE profiles
SET admin_roles = NULL
WHERE is_admin = true
  AND admin_roles = ARRAY['admin:super'];

DO $$
DECLARE
  affected INT;
BEGIN
  GET DIAGNOSTICS affected = ROW_COUNT;
  RAISE NOTICE 'RBAC-FASE2 rollback: % profiles reverted from admin:super', affected;
END $$;
