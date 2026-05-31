-- ============================================================================
-- UP: NETINT-002 — network_sector_migration RPC
-- Issue: #1284
-- Wave: NETINT Wave 0 — RPC de migracao setorial
-- ============================================================================
-- Context:
--   Network Intelligence EPIC (#1263). Detecta padroes de migracao setorial
--   a partir de pncp_supplier_contracts: identifica CNPJs que entram em
--   novos setores nos ultimos N meses.
--
--   "New entrant" no setor X = CNPJ que:
--     1. Teve contratos em QUALQUER setor nos ultimos 24 meses
--     2. NAO teve contratos no setor X antes da janela de analise (24m - p_meses)
--     3. Comecou a ter contratos no setor X nos ultimo p_meses meses
--
--   Coluna setor_classificado adicionada para permitir filtragem setorial
--   O(1). Nullable — populada por pipeline de classificacao futura.
--
--   SECURITY DEFINER + SET search_path = public, pg_temp (SEC-SECDEF-001/002).
--   GRANT para anon, authenticated, service_role — output agregado publico.
-- ============================================================================

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- 1. Add setor_classificado column to pncp_supplier_contracts
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.pncp_supplier_contracts
    ADD COLUMN IF NOT EXISTS setor_classificado TEXT;

COMMENT ON COLUMN public.pncp_supplier_contracts.setor_classificado IS
    'NETINT-002: Setor classificado do contrato. Nullable — populado por pipeline externo.';

-- Composite index: sector + date covers the RPC WHERE clauses
CREATE INDEX IF NOT EXISTS idx_psc_setor_data
    ON public.pncp_supplier_contracts (setor_classificado, data_assinatura DESC)
    WHERE setor_classificado IS NOT NULL AND is_active = TRUE;

-- ────────────────────────────────────────────────────────────────────────────
-- 2. RPC: network_sector_migration
-- ────────────────────────────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION public.network_sector_migration(
    p_setor TEXT DEFAULT NULL,
    p_uf VARCHAR(2) DEFAULT NULL,
    p_meses INT DEFAULT 12
)
RETURNS JSON
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_result          JSON;
    v_window_start    DATE;
    v_baseline_start  DATE;
    v_uf_clean        TEXT;
    v_period_start    TEXT;
    v_period_end      TEXT;
BEGIN
    -- ── Input Validation ────────────────────────────────────────────────
    IF p_meses IS NULL OR p_meses < 1 OR p_meses > 24 THEN
        RAISE EXCEPTION 'p_meses must be between 1 and 24, got %', p_meses;
    END IF;

    IF p_uf IS NOT NULL THEN
        v_uf_clean := UPPER(TRIM(p_uf));
        IF v_uf_clean !~ '^[A-Z]{2}$' THEN
            RAISE EXCEPTION 'p_uf must be a 2-letter state code, got %', p_uf;
        END IF;
    END IF;

    IF p_setor IS NOT NULL AND LENGTH(TRIM(p_setor)) = 0 THEN
        RAISE EXCEPTION 'p_setor cannot be empty string';
    END IF;

    -- ── Timeout Defense ─────────────────────────────────────────────────
    SET LOCAL statement_timeout = '15s';

    -- ── Date Windows ────────────────────────────────────────────────────
    -- Total window: 24 months ending today
    -- Baseline:     [today - 24m, today - p_meses) — sectors CNPJ was active in
    -- Analysis:     [today - p_meses, today]       — sectors CNPJ is entering
    v_window_start := (CURRENT_DATE - (p_meses || ' months')::INTERVAL)::DATE;
    v_baseline_start := (CURRENT_DATE - INTERVAL '24 months')::DATE;

    v_period_start := TO_CHAR(v_window_start, 'YYYY-MM');
    v_period_end   := TO_CHAR(CURRENT_DATE, 'YYYY-MM');

    -- ── Main Query ──────────────────────────────────────────────────────
    WITH
    -- Baseline setorial: setores em que cada CNPJ operou ANTES da janela de analise
    baseline_sectors AS (
        SELECT DISTINCT ni_fornecedor, setor_classificado
        FROM public.pncp_supplier_contracts
        WHERE is_active = TRUE
          AND setor_classificado IS NOT NULL
          AND data_assinatura >= v_baseline_start
          AND data_assinatura < v_window_start
          AND (v_uf_clean IS NULL OR uf = v_uf_clean)
          AND (p_setor IS NULL OR setor_classificado = p_setor)
    ),
    -- Condicao 1: CNPJs ativos em QUALQUER setor nos ultimos 24 meses
    active_cnpjs AS (
        SELECT DISTINCT ni_fornecedor
        FROM public.pncp_supplier_contracts
        WHERE is_active = TRUE
          AND data_assinatura >= v_baseline_start
          AND (v_uf_clean IS NULL OR uf = v_uf_clean)
    ),
    -- Janela de analise: contratos nos ultimos p_meses meses
    window_contracts AS (
        SELECT DISTINCT ni_fornecedor, setor_classificado, uf, valor_global
        FROM public.pncp_supplier_contracts
        WHERE is_active = TRUE
          AND setor_classificado IS NOT NULL
          AND data_assinatura >= v_window_start
          AND (v_uf_clean IS NULL OR uf = v_uf_clean)
    ),
    -- New entrants: CNPJs que entram em setores novos (condicoes 1+2+3)
    new_entrants AS (
        SELECT wc.ni_fornecedor, wc.setor_classificado, wc.uf, wc.valor_global
        FROM window_contracts wc
        JOIN active_cnpjs ac ON ac.ni_fornecedor = wc.ni_fornecedor
        WHERE NOT EXISTS (
            SELECT 1 FROM baseline_sectors bs
            WHERE bs.ni_fornecedor = wc.ni_fornecedor
              AND bs.setor_classificado = wc.setor_classificado
        )
        AND (
            p_setor IS NULL
            OR EXISTS (
                SELECT 1 FROM baseline_sectors bs2
                WHERE bs2.ni_fornecedor = wc.ni_fornecedor
            )
        )
    ),
    -- Total historico de CNPJs por setor (baseline)
    historical AS (
        SELECT setor_classificado, COUNT(DISTINCT ni_fornecedor) AS total_historicos
        FROM baseline_sectors
        GROUP BY setor_classificado
    ),
    -- Agregacao de new entrants por setor de destino
    tendencias_agg AS (
        SELECT
            ne.setor_classificado AS sector_id,
            COUNT(DISTINCT ne.ni_fornecedor) AS novos_entrantes,
            COALESCE(h.total_historicos, 0) AS total_historicos,
            COALESCE(AVG(ne.valor_global), 0) AS ticket_medio,
            (
                SELECT ARRAY_AGG(uf_agg.uf ORDER BY uf_agg.cnt DESC)
                FROM (
                    SELECT ne2.uf, COUNT(*) AS cnt
                    FROM new_entrants ne2
                    WHERE ne2.setor_classificado = ne.setor_classificado
                      AND ne2.uf IS NOT NULL
                    GROUP BY ne2.uf
                    ORDER BY cnt DESC
                    LIMIT 3
                ) uf_agg
            ) AS ufs_principais
        FROM new_entrants ne
        LEFT JOIN historical h ON h.setor_classificado = ne.setor_classificado
        GROUP BY ne.setor_classificado, h.total_historicos
    )
    -- Montagem do JSON final
    SELECT JSON_BUILD_OBJECT(
        'setor_referencia', p_setor,
        'tendencias', COALESCE(
            (SELECT JSON_AGG(
                JSON_BUILD_OBJECT(
                    'setor_destino', t.sector_id,
                    'novos_entrantes', t.novos_entrantes,
                    'crescimento_percentual', ROUND(
                        CASE
                            WHEN t.total_historicos > 0
                            THEN t.novos_entrantes::NUMERIC / t.total_historicos
                            ELSE 0
                        END::NUMERIC, 4
                    ),
                    'ufs_principais', COALESCE(t.ufs_principais, ARRAY[]::TEXT[]),
                    'ticket_medio_setor_destino', ROUND(t.ticket_medio, 2),
                    'sinal', CASE
                        WHEN t.total_historicos > 0
                             AND t.novos_entrantes::NUMERIC / t.total_historicos > 0.1
                        THEN 'alta'
                        ELSE 'estavel'
                    END
                )
                ORDER BY t.novos_entrantes DESC
            )
            FROM tendencias_agg t
            WHERE (p_setor IS NULL OR t.sector_id <> p_setor)),
            '[]'::JSON
        ),
        'stats', JSON_BUILD_OBJECT(
            'periodo_analise', v_period_start || ' a ' || v_period_end,
            'total_migracoes_detectadas', COALESCE(
                (SELECT SUM(t.novos_entrantes)
                 FROM tendencias_agg t
                 WHERE (p_setor IS NULL OR t.sector_id <> p_setor)),
                0
            ),
            'setores_mais_quentes', COALESCE(
                (SELECT JSON_AGG(t.sector_id ORDER BY t.novos_entrantes DESC)
                 FROM (
                     SELECT sector_id, novos_entrantes
                     FROM tendencias_agg
                     WHERE (p_setor IS NULL OR sector_id <> p_setor)
                     ORDER BY novos_entrantes DESC
                     LIMIT 3
                 ) t),
                '[]'::JSON
            )
        )
    ) INTO v_result;

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.network_sector_migration(TEXT, VARCHAR, INTEGER) IS
    'NETINT-002 — Detecta padroes de migracao setorial em pncp_supplier_contracts. Dados publicos agregados, sem exposicao de CNPJ individual.';

GRANT EXECUTE ON FUNCTION public.network_sector_migration(TEXT, VARCHAR, INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION public.network_sector_migration(TEXT, VARCHAR, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION public.network_sector_migration(TEXT, VARCHAR, INTEGER) TO service_role;

COMMIT;
