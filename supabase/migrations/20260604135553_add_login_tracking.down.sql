-- ============================================================================
-- DOWN: LIFECYCLE-001 — reverts login tracking columns and login_activity table
-- Reverses: 20260604135553_add_login_tracking.sql
-- Date: 2026-06-04
-- ============================================================================
-- Context:
--   Remove login tracking columns (last_login_at, login_count) from profiles
--   and drops the login_activity table. Reverses all RLS policies, indexes,
--   grants, and comments added by the up migration.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Drop RLS policies (must exist before dropping table)
-- ============================================================================

DROP POLICY IF EXISTS "login_activity_select_own" ON public.login_activity;
DROP POLICY IF EXISTS "login_activity_service_select" ON public.login_activity;
DROP POLICY IF EXISTS "login_activity_service_insert" ON public.login_activity;
DROP POLICY IF EXISTS "login_activity_service_update" ON public.login_activity;
DROP POLICY IF EXISTS "login_activity_service_delete" ON public.login_activity;

-- ============================================================================
-- 2. Drop index
-- ============================================================================

DROP INDEX IF EXISTS public.idx_login_activity_user_date;

-- ============================================================================
-- 3. Drop table
-- ============================================================================

DROP TABLE IF EXISTS public.login_activity CASCADE;

-- ============================================================================
-- 4. Revoke grants (cleanup; table is gone, but explicit for audit)
-- ============================================================================

REVOKE ALL ON public.login_activity FROM authenticated;
REVOKE ALL ON public.login_activity FROM service_role;

-- ============================================================================
-- 5. Drop columns from profiles
-- ============================================================================

ALTER TABLE public.profiles
    DROP COLUMN IF EXISTS last_login_at,
    DROP COLUMN IF EXISTS login_count;

-- ============================================================================

NOTIFY pgrst, 'reload schema';

COMMIT;
