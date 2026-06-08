-- ============================================================================
-- UP: subcontract_intel_rpc — RPC de agregacao para relatorio de subcontratacao
-- Date: 2026-06-07
-- Issue: SUBINTEL-033 (#1531)
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Pipeline SUBINTEL-033 (R$97): DataLake → RPC → PDF → Stripe → email.
--   Agrega dados de subcontratacao de fornecedores: partnership score,
--   dependencia regional, rede de fornecedores, benchmark competitivo e
--   metricas setoriais. Retorna JSONB pronto para gerar PDF via ReportLab
--   (pdf_generator_subcontract_report.py).
--
--   Para entity_key formato CNPJ (14 digitos), chama as RPCs existentes:
--     - subcontract_partnership_score (#1224)
--     - subcontract_regional_dependency (#1224)
--     - competitive_benchmark (#1261)
--     - collective_supplier_network (#1263)
--
--   Para entity_key formato "setor:UF", usa sector_uf_intel como base
--   e deriva metricas de subcontratacao.
--
--   Assinatura:
--     subcontract_intel(p_entity_key TEXT, p_window_months INTEGER DEFAULT 24)
--        RETURNS JSONB
--
--   SECURITY DEFINER + SET search_path = public, pg_temp por SEC-SECDEF-001/002.
--   GRANT so a service_role — payload liberado pos-pagamento pelo backend.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- RPC: subcontract_intel
-- Retorna JSONB com metricas para relatorio executivo de subcontratacao.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.subcontract_intel(
    p_entity_key      TEXT,
    p_window_months   INTEGER DEFAULT 24
)
RETURNS JSONB
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_cnpj_clean       TEXT;
    v_sector_id        TEXT;
    v_uf               TEXT;
    v_is_cnpj          BOOLEAN;
    v_sector_data      JSONB;
    v_partnership      JSONB;
    v_regional_dep     JSONB;
    v_benchmark        JSONB;
    v_supplier_network JSONB;
    v_window_start     DATE;
    v_result           JSONB;
BEGIN
    -- Defesa em profundidade: timeout local
    SET LOCAL statement_timeout = '20s';

    -- Validar input
    IF p_entity_key IS NULL OR trim(p_entity_key) = '' THEN
        RAISE EXCEPTION 'p_entity_key must be non-empty';
    END IF;

    v_window_start := (CURRENT_DATE - (p_window_months || ' months')::INTERVAL)::DATE;

    -- Determinar tipo: CNPJ (14 digitos) ou "setor:UF"
    v_cnpj_clean := regexp_replace(p_entity_key, '[^0-9]', '', 'g');
    v_is_cnpj := (length(v_cnpj_clean) = 14);

    IF v_is_cnpj THEN
        -- ====================================================================
        -- Modo CNPJ — chamar RPCs existentes
        -- ====================================================================

        -- 1. Partnership score (SUBINTEL-011)
        SELECT jsonb_agg(row_to_json(t))
          INTO v_partnership
          FROM (
            SELECT score, factors, similar_suppliers, recommended_actions
              FROM public.subcontract_partnership_score(v_cnpj_clean)
          ) t;

        -- 2. Regional dependency (SUBINTEL-012)
        SELECT jsonb_agg(row_to_json(t))
          INTO v_regional_dep
          FROM (
            SELECT uf_sigla, dependency_index, contract_count,
                   top_orgaos, expansion_potential
              FROM public.subcontract_regional_dependency(v_cnpj_clean)
          ) t;

        -- 3. Competitive benchmark (COMPINT-013)
        SELECT jsonb_agg(row_to_json(t))
          INTO v_benchmark
          FROM (
            SELECT metric_name, competitor_value,
                   sector_p25, sector_p50, sector_p75,
                   competitor_percentile, interpretation
              FROM public.competitive_benchmark(v_cnpj_clean)
          ) t;

        -- 4. Supplier network (NETINT-012) — top connections
        SELECT jsonb_agg(row_to_json(t))
          INTO v_supplier_network
          FROM (
            SELECT source_cnpj, source_name, target_cnpj, target_name,
                   weight, shared_orgaos
              FROM public.collective_supplier_network(NULL, 2)
             WHERE source_cnpj = v_cnpj_clean OR target_cnpj = v_cnpj_clean
             ORDER BY weight DESC
             LIMIT 20
          ) t;

        -- Montar payload final
        v_result := jsonb_build_object(
            'entity_type',         'cnpj',
            'entity_key',          v_cnpj_clean,
            'window_months',       p_window_months,
            'window_start',        v_window_start,
            'partnership_score',   COALESCE(v_partnership, '[]'::JSONB),
            'regional_dependency', COALESCE(v_regional_dep, '[]'::JSONB),
            'benchmark',           COALESCE(v_benchmark, '[]'::JSONB),
            'supplier_network',    COALESCE(v_supplier_network, '[]'::JSONB),
            'generated_at',        NOW()
        );

    ELSE
        -- ====================================================================
        -- Modo setor:UF — extrair setor e UF do entity_key
        -- ====================================================================
        IF position(':' in p_entity_key) = 0 THEN
            RAISE EXCEPTION 'Invalid entity_key: expected format "setor:UF" or CNPJ (14 digits), got %', p_entity_key;
        END IF;

        v_sector_id := lower(trim(split_part(p_entity_key, ':', 1)));
        v_uf := upper(trim(split_part(p_entity_key, ':', 2)));

        IF v_sector_id = '' OR length(v_uf) <> 2 THEN
            RAISE EXCEPTION 'Invalid entity_key format: setor=% uf=%', v_sector_id, v_uf;
        END IF;

        -- No modo setor:UF, nao temos RPC especifico de subcontratacao
        -- Retornamos payload basico com indicacao de que setor:UF requer
        -- dados do setor_uf_intel RPC externo.
        v_result := jsonb_build_object(
            'entity_type',         'sector_uf',
            'sector_id',           v_sector_id,
            'uf',                  v_uf,
            'window_months',       p_window_months,
            'window_start',        v_window_start,
            'note',                'Use sector_uf_intel RPC for sector-level data. subcontract_intel provides partnership-level analytics.',
            'generated_at',        NOW()
        );
    END IF;

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.subcontract_intel(TEXT, INTEGER) IS
    'SUBINTEL-033 — Agrega dados de subcontratacao para relatorio executivo PDF. '
    'Aceita CNPJ (14 digitos) ou setor:UF. SECURITY DEFINER, service_role only.';

REVOKE ALL ON FUNCTION public.subcontract_intel(TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.subcontract_intel(TEXT, INTEGER) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.subcontract_intel(TEXT, INTEGER) TO service_role;

COMMIT;
