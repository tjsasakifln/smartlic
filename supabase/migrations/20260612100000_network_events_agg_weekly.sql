-- ============================================================================
-- NETINT-007: Agregacao semanal e politica de retencao network_events
-- Issue: #1677
-- Epic: #1263 (EPIC-NETINT)
-- ============================================================================
-- Context:
--   NETINT-001 criou network_events_agg (agregacao diaria). Sem politica de
--   retencao, a tabela cresce sem limite — custo de armazenamento e degradacao
--   de performance. Esta migration cria:
--
--   1. Tabela network_events_agg_weekly: agregacao semanal dos eventos diarios
--      com mais de 7 dias, compactando 7 registros em 1 com contagem somada
--      e metadados merged.
--   2. Unique constraint: (evento_tipo, dimensao_tipo, dimensao_valor, semana_inicio)
--   3. RLS: SELECT-only policies (dados agregados anonimos)
--   4. Grants para anon, authenticated, service_role
-- ============================================================================

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. Create network_events_agg_weekly table
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.network_events_agg_weekly (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evento_tipo TEXT NOT NULL,
    dimensao_tipo TEXT NOT NULL,
    dimensao_valor TEXT NOT NULL,
    semana_inicio DATE NOT NULL,
    contagem INTEGER DEFAULT 1,
    metadados JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

COMMENT ON TABLE public.network_events_agg_weekly IS
    'NETINT-007: Agregacao semanal de eventos anonimos. 7 registros diarios → 1 semanal, contagem somada, metadados merged.';

COMMENT ON COLUMN public.network_events_agg_weekly.evento_tipo IS
    'Tipo do evento: search_query, sector_view, org_view, cnpj_lookup, discount_view, migration_view, competitor_view';

COMMENT ON COLUMN public.network_events_agg_weekly.dimensao_tipo IS
    'Tipo da dimensao: setor, uf, modalidade, orgao, municipio';

COMMENT ON COLUMN public.network_events_agg_weekly.dimensao_valor IS
    'Valor da dimensao (ex: "saude", "SP", "pregao") — nunca PII';

COMMENT ON COLUMN public.network_events_agg_weekly.semana_inicio IS
    'Data de inicio da semana (segunda-feira) — ISO week start';

COMMENT ON COLUMN public.network_events_agg_weekly.contagem IS
    'Contagem agregada de eventos na semana — soma dos registros diarios';

COMMENT ON COLUMN public.network_events_agg_weekly.metadados IS
    'Metadados merged da semana: {"setores": [], "ufs": [], "modalidades": []}. NUNCA user_id, cnpj, email, ip.';

-- ────────────────────────────────────────────────────────────────────────────
-- 2. Indexes
-- ────────────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_network_events_weekly_semana
    ON public.network_events_agg_weekly (semana_inicio, evento_tipo, dimensao_tipo);

CREATE INDEX IF NOT EXISTS idx_network_events_weekly_tipo_valor
    ON public.network_events_agg_weekly (evento_tipo, dimensao_valor);

-- ────────────────────────────────────────────────────────────────────────────
-- 3. Unique constraint
-- ────────────────────────────────────────────────────────────────────────────

CREATE UNIQUE INDEX IF NOT EXISTS idx_network_events_weekly_unique
    ON public.network_events_agg_weekly (evento_tipo, dimensao_tipo, dimensao_valor, semana_inicio);

ALTER TABLE public.network_events_agg_weekly
    ADD CONSTRAINT network_events_agg_weekly_unique
    UNIQUE USING INDEX idx_network_events_weekly_unique;

-- ────────────────────────────────────────────────────────────────────────────
-- 4. RLS — SELECT-only policies (INSERT via job ARQ com service_role)
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.network_events_agg_weekly ENABLE ROW LEVEL SECURITY;

CREATE POLICY "network_events_agg_weekly_select_anon"
    ON public.network_events_agg_weekly
    FOR SELECT
    TO anon
    USING (true);

CREATE POLICY "network_events_agg_weekly_select_authenticated"
    ON public.network_events_agg_weekly
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "network_events_agg_weekly_select_service_role"
    ON public.network_events_agg_weekly
    FOR SELECT
    TO service_role
    USING (true);

-- ────────────────────────────────────────────────────────────────────────────
-- 5. Grants
-- ────────────────────────────────────────────────────────────────────────────

GRANT SELECT ON public.network_events_agg_weekly TO anon;
GRANT SELECT ON public.network_events_agg_weekly TO authenticated;
GRANT SELECT ON public.network_events_agg_weekly TO service_role;

-- INSERT/UPDATE/DELETE via service_role apenas (job ARQ)
GRANT INSERT, UPDATE, DELETE ON public.network_events_agg_weekly TO service_role;

COMMIT;
