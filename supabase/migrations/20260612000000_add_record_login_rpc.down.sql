-- ============================================================================
-- DOWN: remove record_login RPC function
-- Reverses: 20260612000000_add_record_login_rpc.sql
-- Issue: #1690 — PostgREST PGRST202: record_login RPC missing
-- Date: 2026-06-12
-- ============================================================================
-- Context:
--   Remove the public.record_login RPC function. This reverses the up
--   migration that added the function to fix PGRST202 errors.
--   Only drop if this specific function signature exists.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Drop function
-- ============================================================================

DROP FUNCTION IF EXISTS public.record_login(UUID, DATE, TIMESTAMPTZ);

-- ============================================================================
-- 2. Revoke execution grant (cleanup)
-- ============================================================================

REVOKE EXECUTE ON FUNCTION public.record_login FROM service_role;

-- ============================================================================

NOTIFY pgrst, 'reload schema';

COMMIT;
