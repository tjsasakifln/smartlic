-- ============================================================================
-- CONSULT-001: Consultant Seats — assentos read-only para clientes
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.consultant_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultant_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(consultant_id, client_id)
);

COMMENT ON TABLE public.consultant_clients IS
    'CONSULT-001: Vinculo entre consultor e cliente para seats read-only.';
COMMENT ON COLUMN public.consultant_clients.consultant_id IS
    'ID do consultor (plano Consultoria)';
COMMENT ON COLUMN public.consultant_clients.client_id IS
    'ID do cliente (conta gratuita)';
COMMENT ON COLUMN public.consultant_clients.status IS
    'active | revoked — controle de acesso do consultor';

CREATE TABLE IF NOT EXISTS public.consultant_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultant_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,
    resource_id UUID NOT NULL,
    shared_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.consultant_shares IS
    'CONSULT-001: Recursos compartilhados pelo consultor com cliente.';
COMMENT ON COLUMN public.consultant_shares.consultant_id IS
    'ID do consultor que compartilhou';
COMMENT ON COLUMN public.consultant_shares.client_id IS
    'ID do cliente que recebeu acesso';
COMMENT ON COLUMN public.consultant_shares.resource_type IS
    'Tipo do recurso compartilhado (ex: busca, pipeline, analise)';
COMMENT ON COLUMN public.consultant_shares.resource_id IS
    'ID do recurso compartilhado';

CREATE INDEX IF NOT EXISTS idx_consultant_shares_consultant ON public.consultant_shares(consultant_id);
CREATE INDEX IF NOT EXISTS idx_consultant_shares_client ON public.consultant_shares(client_id);
CREATE INDEX IF NOT EXISTS idx_consultant_clients_consultant ON public.consultant_clients(consultant_id);
CREATE INDEX IF NOT EXISTS idx_consultant_clients_client ON public.consultant_clients(client_id);

ALTER TABLE public.consultant_clients ENABLE ROW LEVEL SECURITY;

CREATE POLICY consultant_clients_select_consultant ON public.consultant_clients
    FOR SELECT USING (consultant_id = auth.uid());
CREATE POLICY consultant_clients_select_client ON public.consultant_clients
    FOR SELECT USING (client_id = auth.uid());
CREATE POLICY consultant_clients_insert_consultant ON public.consultant_clients
    FOR INSERT WITH CHECK (consultant_id = auth.uid());
CREATE POLICY consultant_clients_update_consultant ON public.consultant_clients
    FOR UPDATE USING (consultant_id = auth.uid()) WITH CHECK (consultant_id = auth.uid());

ALTER TABLE public.consultant_shares ENABLE ROW LEVEL SECURITY;

CREATE POLICY consultant_shares_select_consultant ON public.consultant_shares
    FOR SELECT USING (consultant_id = auth.uid());
CREATE POLICY consultant_shares_select_client ON public.consultant_shares
    FOR SELECT USING (client_id = auth.uid());
CREATE POLICY consultant_shares_insert_consultant ON public.consultant_shares
    FOR INSERT WITH CHECK (consultant_id = auth.uid());
CREATE POLICY consultant_shares_delete_consultant ON public.consultant_shares
    FOR DELETE USING (consultant_id = auth.uid());
