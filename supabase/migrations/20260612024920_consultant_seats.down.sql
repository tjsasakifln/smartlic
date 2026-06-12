-- ============================================================================
-- DOWN: Remove consultant seats tables and all associated RLS policies
-- reverses 20260612024920_consultant_seats.sql
-- Date: 2026-06-12
-- ============================================================================

-- Drop RLS policies for consultant_shares
DROP POLICY IF EXISTS consultant_shares_consultant_select ON public.consultant_shares;
DROP POLICY IF EXISTS consultant_shares_client_select ON public.consultant_shares;
DROP POLICY IF EXISTS consultant_shares_consultant_insert ON public.consultant_shares;
DROP POLICY IF EXISTS consultant_shares_consultant_delete ON public.consultant_shares;

-- Drop RLS policies for consultant_clients
DROP POLICY IF EXISTS consultant_clients_consultant_select ON public.consultant_clients;
DROP POLICY IF EXISTS consultant_clients_client_select ON public.consultant_clients;
DROP POLICY IF EXISTS consultant_clients_consultant_insert ON public.consultant_clients;
DROP POLICY IF EXISTS consultant_clients_consultant_update ON public.consultant_clients;

-- Drop indexes
DROP INDEX IF EXISTS public.idx_consultant_shares_consultant_client;
DROP INDEX IF EXISTS public.idx_consultant_shares_client;

-- Drop tables
DROP TABLE IF EXISTS public.consultant_shares;
DROP TABLE IF EXISTS public.consultant_clients;
