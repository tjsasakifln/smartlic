-- CONSULT-001 (#1613): Consultant Seats — tables for consultant-client relationships
-- and resource sharing in the Consultoria plan (R$997/mes).
--
-- consultant_clients: tracks which clients a consultant has invited/approved
-- consultant_shares: tracks which resources (busca, pipeline, analise) are shared

SET statement_timeout = 0;

-- ============================================================================
-- consultant_clients
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
    'CONSULT-001: Tracks consultant-client relationships for the Consultoria plan.';
COMMENT ON COLUMN public.consultant_clients.consultant_id IS 'The consultant (Consultoria subscriber)';
COMMENT ON COLUMN public.consultant_clients.client_id IS 'The client (free-tier user)';
COMMENT ON COLUMN public.consultant_clients.status IS 'active | revoked';

-- ============================================================================
-- consultant_shares
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.consultant_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consultant_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    client_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,
    resource_id UUID NOT NULL,
    shared_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.consultant_shares IS
    'CONSULT-001: Resources shared from consultant to client.';
COMMENT ON COLUMN public.consultant_shares.resource_type IS 'Resource type: busca, pipeline, analise';
COMMENT ON COLUMN public.consultant_shares.resource_id IS 'UUID of the shared resource';

CREATE INDEX IF NOT EXISTS idx_consultant_shares_consultant_client
    ON public.consultant_shares (consultant_id, client_id);
CREATE INDEX IF NOT EXISTS idx_consultant_shares_client
    ON public.consultant_shares (client_id);

-- ============================================================================
-- RLS: consultant_clients
-- ============================================================================

ALTER TABLE public.consultant_clients ENABLE ROW LEVEL SECURITY;

-- Consultant can read their own client relationships
CREATE POLICY consultant_clients_consultant_select ON public.consultant_clients
    FOR SELECT
    USING (consultant_id = auth.uid());

-- Client can read their own relationship (to see who their consultant is)
CREATE POLICY consultant_clients_client_select ON public.consultant_clients
    FOR SELECT
    USING (client_id = auth.uid());

-- Consultant can insert (invite) new clients
CREATE POLICY consultant_clients_consultant_insert ON public.consultant_clients
    FOR INSERT
    WITH CHECK (consultant_id = auth.uid());

-- Consultant can update (revoke) their own client relationships
CREATE POLICY consultant_clients_consultant_update ON public.consultant_clients
    FOR UPDATE
    USING (consultant_id = auth.uid());

-- ============================================================================
-- RLS: consultant_shares
-- ============================================================================

ALTER TABLE public.consultant_shares ENABLE ROW LEVEL SECURITY;

-- Consultant can manage their own shares
CREATE POLICY consultant_shares_consultant_select ON public.consultant_shares
    FOR SELECT
    USING (consultant_id = auth.uid());

-- Client can read shares directed to them
CREATE POLICY consultant_shares_client_select ON public.consultant_shares
    FOR SELECT
    USING (client_id = auth.uid());

-- Consultant can insert shares
CREATE POLICY consultant_shares_consultant_insert ON public.consultant_shares
    FOR INSERT
    WITH CHECK (consultant_id = auth.uid());

-- Consultant can delete shares
CREATE POLICY consultant_shares_consultant_delete ON public.consultant_shares
    FOR DELETE
    USING (consultant_id = auth.uid());
