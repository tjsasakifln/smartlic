-- ============================================================================
-- Migration: 20260612120000_add_record_login_rpc
-- Issue: #1690 — PGRST202: record_login RPC not found in schema cache
-- Date: 2026-06-12
--
-- Purpose:
--   Creates the public.record_login RPC function that is called by
--   login_tracker.py::_flush_batch to persist login activity from the
--   Redis write-behind buffer to PostgreSQL.
--
--   The migration 20260604135553_add_login_tracking created the profiles
--   columns (last_login_at, login_count) and the login_activity table, but
--   did not create the RPC function that login_tracker.py actually calls.
--
--   This RPC is idempotent: calling it with the same (user_id, login_date)
--   multiple times will safely increment login_count (duplicate detection
--   is done at the Redis layer before flush).
--
--   SECURITY DEFINER ensures the function runs with service_role privileges
--   even when called by authenticated users via PostgREST.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.record_login(
    p_user_id UUID,
    p_login_date DATE,
    p_last_login_at TIMESTAMPTZ
) RETURNS void
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public
AS $$
BEGIN
    -- Update profile login tracking columns
    UPDATE public.profiles
    SET last_login_at = p_last_login_at,
        login_count = login_count + 1
    WHERE id = p_user_id;

    -- Insert audit record
    INSERT INTO public.login_activity (user_id, logged_in_at)
    VALUES (p_user_id, p_last_login_at);
END;
$$;

-- Grant execute to service_role (backend uses service_role key)
REVOKE EXECUTE ON FUNCTION public.record_login(UUID, DATE, TIMESTAMPTZ) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.record_login(UUID, DATE, TIMESTAMPTZ) TO service_role;

COMMENT ON FUNCTION public.record_login IS
    'LIFECYCLE-001/#1690: Records a login event. Updates profiles.last_login_at '
    'and login_count, and inserts into login_activity. Called by login_tracker.py '
    'via PostgREST RPC. SECURITY DEFINER — runs as owner.';

-- Notify PostgREST to reload schema cache
NOTIFY pgrst, 'reload schema';
