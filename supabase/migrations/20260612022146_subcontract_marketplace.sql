-- ============================================================================
-- MKT-001 (#1616): Subcontract Marketplace MVP
--
-- Purpose:
--   Cria as tabelas de marketplace de subcontratacao B2G:
--   - subcontract_opportunities: oportunidades identificadas automaticamente
--     com base em heuristicas de contratos publicos
--   - subcontract_interests: manifestacao de interesse de fornecedores
--     em oportunidades especificas
--
-- Dependencias:
--   - profiles table (FK) - ja existente
--   - pncp_supplier_contracts table (FK) - ja existente
--
-- Seguranca:
--   - RLS habilitado em ambas as tabelas
--   - subcontract_opportunities: SELECT publico (para vitrine),
--     INSERT/UPDATE/DELETE apenas service_role (job ARQ)
--   - subcontract_interests: SELECT proprio + INSERT autenticado,
--     UPDATE/DELETE apenas service_role
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- Table: subcontract_opportunities
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subcontract_opportunities (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id     UUID REFERENCES pncp_supplier_contracts(id) ON DELETE CASCADE,
    winner_cnpj     TEXT NOT NULL,
    winner_name     TEXT,
    sector          TEXT,
    value           DECIMAL(15,2),
    services_needed TEXT[] DEFAULT '{}',
    status          TEXT NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'matched', 'closed')),
    uf              TEXT,
    municipio       TEXT,
    orgao_nome      TEXT,
    objeto          TEXT,
    discovery_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for filtering and listing
CREATE INDEX IF NOT EXISTS idx_subcontract_opportunities_status
    ON subcontract_opportunities (status);
CREATE INDEX IF NOT EXISTS idx_subcontract_opportunities_sector
    ON subcontract_opportunities (sector);
CREATE INDEX IF NOT EXISTS idx_subcontract_opportunities_uf
    ON subcontract_opportunities (uf);
CREATE INDEX IF NOT EXISTS idx_subcontract_opportunities_created_at
    ON subcontract_opportunities (created_at DESC);

-- Comments
COMMENT ON TABLE subcontract_opportunities IS
  'MKT-001: Oportunidades de subcontratacao identificadas automaticamente. '
  'Preenchido pelo job ARQ diario subcontract_discovery_job.';
COMMENT ON COLUMN subcontract_opportunities.contract_id IS
  'FK para pncp_supplier_contracts — contrato original que gerou a oportunidade';
COMMENT ON COLUMN subcontract_opportunities.winner_cnpj IS
  'CNPJ do vencedor do contrato original';
COMMENT ON COLUMN subcontract_opportunities.winner_name IS
  'Nome razao social do vencedor';
COMMENT ON COLUMN subcontract_opportunities.services_needed IS
  'Lista de servicos/especialidades necessarias para subcontratacao';
COMMENT ON COLUMN subcontract_opportunities.status IS
  'Status: open (disponivel), matched (interesse em andamento), closed (fechado/arquivado)';
COMMENT ON COLUMN subcontract_opportunities.discovery_reason IS
  'Resumo textual da heuristica que identificou esta oportunidade';

-- ────────────────────────────────────────────────────────────────────────────
-- Table: subcontract_interests
-- ────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subcontract_interests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_id  UUID NOT NULL REFERENCES subcontract_opportunities(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    message         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(opportunity_id, user_id)
);

-- Index for listing user's interests
CREATE INDEX IF NOT EXISTS idx_subcontract_interests_user_id
    ON subcontract_interests (user_id);
CREATE INDEX IF NOT EXISTS idx_subcontract_interests_opportunity_id
    ON subcontract_interests (opportunity_id);

-- Comments
COMMENT ON TABLE subcontract_interests IS
  'MKT-001: Manifestacoes de interesse de fornecedores em oportunidades de subcontratacao. '
  'UNIQUE(opportunity_id, user_id) — cada usuario pode se interessar uma unica vez por oportunidade.';

-- ────────────────────────────────────────────────────────────────────────────
-- RLS — subcontract_opportunities
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE subcontract_opportunities ENABLE ROW LEVEL SECURITY;

-- Public read: any authenticated user can see open opportunities
DROP POLICY IF EXISTS "opportunities_select_public" ON subcontract_opportunities;
CREATE POLICY "opportunities_select_public" ON subcontract_opportunities
    FOR SELECT
    USING (status = 'open');

-- Service role: full control
DROP POLICY IF EXISTS "opportunities_service_role" ON subcontract_opportunities;
CREATE POLICY "opportunities_service_role" ON subcontract_opportunities
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ────────────────────────────────────────────────────────────────────────────
-- RLS — subcontract_interests
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE subcontract_interests ENABLE ROW LEVEL SECURITY;

-- Users see only their own interests
DROP POLICY IF EXISTS "interests_select_own" ON subcontract_interests;
CREATE POLICY "interests_select_own" ON subcontract_interests
    FOR SELECT
    USING (user_id = auth.uid());

-- Authenticated users can insert their own interest
DROP POLICY IF EXISTS "interests_insert_own" ON subcontract_interests;
CREATE POLICY "interests_insert_own" ON subcontract_interests
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Service role: full control
DROP POLICY IF EXISTS "interests_service_role" ON subcontract_interests;
CREATE POLICY "interests_service_role" ON subcontract_interests
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ────────────────────────────────────────────────────────────────────────────
-- Grant permissions
-- ────────────────────────────────────────────────────────────────────────────
GRANT ALL ON subcontract_opportunities TO service_role, anon, authenticated;
GRANT ALL ON subcontract_interests TO service_role, authenticated;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO service_role, anon, authenticated;
