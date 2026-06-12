-- ============================================================================
-- DOWN: Consultant Seats
-- ============================================================================

DROP POLICY IF EXISTS consultant_shares_delete_consultant ON public.consultant_shares;
DROP POLICY IF EXISTS consultant_shares_insert_consultant ON public.consultant_shares;
DROP POLICY IF EXISTS consultant_shares_select_client ON public.consultant_shares;
DROP POLICY IF EXISTS consultant_shares_select_consultant ON public.consultant_shares;
ALTER TABLE public.consultant_shares DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS consultant_clients_update_consultant ON public.consultant_clients;
DROP POLICY IF EXISTS consultant_clients_insert_consultant ON public.consultant_clients;
DROP POLICY IF EXISTS consultant_clients_select_client ON public.consultant_clients;
DROP POLICY IF EXISTS consultant_clients_select_consultant ON public.consultant_clients;
ALTER TABLE public.consultant_clients DISABLE ROW LEVEL SECURITY;

DROP INDEX IF EXISTS idx_consultant_clients_client;
DROP INDEX IF EXISTS idx_consultant_clients_consultant;
DROP INDEX IF EXISTS idx_consultant_shares_client;
DROP INDEX IF EXISTS idx_consultant_shares_consultant;

DROP TABLE IF EXISTS public.consultant_shares;
DROP TABLE IF EXISTS public.consultant_clients;
