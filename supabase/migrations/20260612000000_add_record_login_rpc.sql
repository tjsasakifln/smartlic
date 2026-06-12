-- ============================================================================
-- Migration: 20260612000000_add_record_login_rpc
-- Issue: #1690 — PostgREST PGRST202: record_login RPC missing
-- Date: 2026-06-12
--
-- Purpose:
--   Cria a função RPC public.record_login que é chamada pelo
--   backend/login_tracker.py para flushear eventos de login.
--
--   A migration original (20260604135553_add_login_tracking.sql) adicionou
--   as colunas e a tabela, mas nunca criou o RPC, causando:
--     PGRST202: Could not find the function public.record_login(...)
--     in the schema cache
--
--   A função:
--     1. Atualiza profiles.last_login_at e incrementa login_count
--     2. Insere registro em login_activity para auditoria
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Create record_login RPC function
-- ============================================================================

CREATE OR REPLACE FUNCTION public.record_login(
    p_user_id UUID,
    p_login_date DATE,
    p_last_login_at TIMESTAMPTZ
) RETURNS void AS $$
BEGIN
    UPDATE public.profiles
    SET last_login_at = p_last_login_at,
        login_count = COALESCE(login_count, 0) + 1
    WHERE id = p_user_id;

    INSERT INTO public.login_activity (user_id, logged_in_at)
    VALUES (p_user_id, p_last_login_at);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION public.record_login IS
    'LIFECYCLE-001: Registra evento de login bem-sucedido. '
    'Atualiza profiles.last_login_at e login_count, e insere '
    'registro em login_activity. Chamado pelo backend/login_tracker.py.';

-- ============================================================================
-- 2. Grant execution to service_role
-- ============================================================================

GRANT EXECUTE ON FUNCTION public.record_login TO service_role;

-- ============================================================================
-- 3. Notify PostgREST to reload schema cache
-- ============================================================================

NOTIFY pgrst, 'reload schema';

COMMIT;
