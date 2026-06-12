-- ============================================================================
-- DOWN: Drops the public.record_login RPC function
-- Reverses: 20260612120000_add_record_login_rpc.sql
-- Date: 2026-06-12
--
-- Removes the SECURITY DEFINER function created to persist login activity
-- from the Redis write-behind buffer to PostgreSQL.
-- ============================================================================

DROP FUNCTION IF EXISTS public.record_login(UUID, DATE, TIMESTAMPTZ);

NOTIFY pgrst, 'reload schema';
