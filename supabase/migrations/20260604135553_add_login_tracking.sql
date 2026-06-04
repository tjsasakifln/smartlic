-- ============================================================================
-- Migration: 20260604135553_add_login_tracking
-- Issue: #1426 — LIFECYCLE-001: login tracking for profiles
-- Date: 2026-06-04
--
-- Purpose:
--   Adiciona colunas de tracking de login na tabela profiles e cria a tabela
--   login_activity para auditoria de login dos usuários.
--
--   Profiles:
--     - last_login_at TIMESTAMPTZ: timestamp do último login bem-sucedido
--     - login_count INTEGER DEFAULT 0: contador total de logins
--
--   login_activity:
--     - Tabela de auditoria com um registro por evento de login
--     - user_id FK para profiles(id)
--     - logged_in_at TIMESTAMPTZ: timestamp do evento de login
--     - Índice composto (user_id, logged_in_at) para queries de coorte
--
--   RLS: Usuário autenticado vê apenas seus próprios registros.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. Add login tracking columns to profiles
-- ============================================================================

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS login_count INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN public.profiles.last_login_at IS
    'LIFECYCLE-001: Timestamp do último login bem-sucedido do usuário. '
    'Atualizado pelo backend no evento de login. NULL se nunca logou.';

COMMENT ON COLUMN public.profiles.login_count IS
    'LIFECYCLE-001: Contador total de logins bem-sucedidos. '
    'Incrementado pelo backend a cada login. Default 0.';

-- ============================================================================
-- 2. Create login_activity table
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.login_activity (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID         NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    logged_in_at TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.login_activity IS
    'LIFECYCLE-001: Auditoria de login dos usuários. Um registro por evento de '
    'login bem-sucedido. Usado para análises de coorte e tracking de atividade.';

COMMENT ON COLUMN public.login_activity.user_id IS
    'FK para profiles(id). Identifica o usuário que realizou o login.';

COMMENT ON COLUMN public.login_activity.logged_in_at IS
    'Timestamp do evento de login. Default now().';

-- ============================================================================
-- 3. Index for cohort queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_login_activity_user_date
    ON public.login_activity (user_id, logged_in_at);

COMMENT ON INDEX public.idx_login_activity_user_date IS
    'LIFECYCLE-001: Índice composto para queries de coorte e histórico de '
    'login por usuário. Cobre (user_id, logged_in_at).';

-- ============================================================================
-- 4. RLS
-- ============================================================================

ALTER TABLE public.login_activity ENABLE ROW LEVEL SECURITY;

-- User can see own login activity
CREATE POLICY "login_activity_select_own" ON public.login_activity
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- service_role full access for backend operations
CREATE POLICY "login_activity_service_select" ON public.login_activity
    FOR SELECT
    TO service_role
    USING (true);

CREATE POLICY "login_activity_service_insert" ON public.login_activity
    FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "login_activity_service_update" ON public.login_activity
    FOR UPDATE
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "login_activity_service_delete" ON public.login_activity
    FOR DELETE
    TO service_role
    USING (true);

-- ============================================================================
-- 5. Grants
-- ============================================================================

GRANT SELECT ON public.login_activity TO authenticated;
GRANT ALL ON public.login_activity TO service_role;

-- ============================================================================
-- 6. Notify PostgREST to reload schema
-- ============================================================================

NOTIFY pgrst, 'reload schema';

COMMIT;
