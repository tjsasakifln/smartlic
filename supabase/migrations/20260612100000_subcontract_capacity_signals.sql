-- ============================================================================
-- UP: subcontract_capacity_signals — RPC for Subcontracting Capacity Analysis
-- Date: 2026-06-12
-- Issue: #1668 (SUBINTEL-001)
-- Parent: #1224 (EPIC-SUBINTEL)
-- ============================================================================
-- Context:
--   SUBINTEL-001: First RPC of the SUBINTEL data layer. Extracts capacity
--   signals from pncp_supplier_contracts (~2-4M rows):
--
--     signal_repeat_winner       — supplier repeatedly wins with same orgao
--     signal_large_contract      — avg contract > sector median (R$5M threshold)
--     signal_subcontracting_pattern — object mentions co-occurrence patterns
--     overall_capacity_score     — weighted avg (0.3/0.4/0.3)
--
--   SECURITY DEFINER + SET search_path = public, pg_temp is mandatory per
--   SEC-SECDEF-001/002. GRANT to service_role only.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION public.subcontract_capacity_signals(
    p_cnpj  VARCHAR(14),
    p_limit INT DEFAULT 50
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_total_contracts      BIGINT;
    v_total_value          NUMERIC;
    v_same_orgao_count     BIGINT;
    v_top_orgao_cnpj       TEXT;
    v_top_orgao_nome       TEXT;
    v_contracts_above_5m   BIGINT;

    -- Scores (0-1)
    v_repeat_winner_score       NUMERIC;
    v_large_contract_score      NUMERIC;
    v_subcontracting_score      NUMERIC;
    v_overall_capacity_score    NUMERIC;

    -- JSONB aggregations
    v_orgaos_list              JSONB;
    v_recent_large_list        JSONB;
    v_related_suppliers_list   JSONB;
BEGIN
    -- Defesa em profundidade: timeout local de 15s
    SET LOCAL statement_timeout = '15s';

    -- Validate input
    IF p_cnpj IS NULL OR length(trim(p_cnpj)) = 0 THEN
        RAISE EXCEPTION 'p_cnpj is required and must be a non-empty string';
    END IF;

    -- Limit bounds
    IF p_limit < 1 THEN
        p_limit := 1;
    ELSIF p_limit > 200 THEN
        p_limit := 200;
    END IF;

    -- ═══════════════════════════════════════════════════════════════════════
    -- Base metrics for the supplier
    -- ═══════════════════════════════════════════════════════════════════════
    SELECT
        COUNT(*)::BIGINT,
        COALESCE(SUM(valor_global), 0)::NUMERIC
    INTO v_total_contracts, v_total_value
    FROM public.pncp_supplier_contracts
    WHERE ni_fornecedor = p_cnpj
      AND is_active = TRUE;

    -- If no contracts, return zeroed result
    IF v_total_contracts = 0 THEN
        RETURN jsonb_build_object(
            'cnpj',                  p_cnpj,
            'total_contracts',       0,
            'total_value',           0,
            'signal_repeat_winner',  jsonb_build_object('score', 0, 'same_orgao_count', 0, 'orgaos', '[]'::JSONB),
            'signal_large_contract', jsonb_build_object('score', 0, 'contracts_above_5m', 0, 'recent_large', '[]'::JSONB),
            'signal_subcontracting_pattern', jsonb_build_object('score', 0, 'cnae_diversity', 0, 'related_suppliers', '[]'::JSONB),
            'overall_capacity_score', 0
        );
    END IF;

    -- ═══════════════════════════════════════════════════════════════════════
    -- Signal 1: repeat_winner — concentration in a single orgao
    -- ═══════════════════════════════════════════════════════════════════════
    -- Find the orgao with the most contracts
    SELECT
        COUNT(*)::BIGINT,
        orgao_cnpj,
        MAX(orgao_nome)
    INTO v_same_orgao_count, v_top_orgao_cnpj, v_top_orgao_nome
    FROM public.pncp_supplier_contracts
    WHERE ni_fornecedor = p_cnpj
      AND is_active = TRUE
      AND orgao_cnpj IS NOT NULL
    GROUP BY orgao_cnpj
    ORDER BY COUNT(*) DESC
    LIMIT 1;

    -- Score: proportion of total contracts won by the top orgao
    -- If no orgao data, score = 0
    IF v_same_orgao_count IS NULL OR v_total_contracts = 0 THEN
        v_repeat_winner_score := 0;
    ELSE
        v_repeat_winner_score := LEAST(v_same_orgao_count::NUMERIC / v_total_contracts::NUMERIC, 1.0);
    END IF;

    -- Top orgaos list (limit 10)
    SELECT COALESCE(
        jsonb_agg(entry ORDER BY (entry->>'count')::BIGINT DESC),
        '[]'::JSONB
    )
    INTO v_orgaos_list
    FROM (
        SELECT jsonb_build_object(
            'nome',        MAX(orgao_nome),
            'count',       COUNT(*)::BIGINT,
            'total_value', COALESCE(SUM(valor_global), 0)::NUMERIC
        ) AS entry
        FROM public.pncp_supplier_contracts
        WHERE ni_fornecedor = p_cnpj
          AND is_active = TRUE
          AND orgao_cnpj IS NOT NULL
        GROUP BY orgao_cnpj
        ORDER BY COUNT(*) DESC
        LIMIT 10
    ) sub;

    -- ═══════════════════════════════════════════════════════════════════════
    -- Signal 2: large_contract — contracts > R$5M
    -- ═══════════════════════════════════════════════════════════════════════
    SELECT COUNT(*)::BIGINT
    INTO v_contracts_above_5m
    FROM public.pncp_supplier_contracts
    WHERE ni_fornecedor = p_cnpj
      AND is_active = TRUE
      AND valor_global > 5000000;

    -- Score: proportion of contracts above 5M, capped at 1.0
    v_large_contract_score := LEAST(v_contracts_above_5m::NUMERIC / GREATEST(v_total_contracts, 1)::NUMERIC, 1.0);

    -- Recent large contracts list (top 5)
    SELECT COALESCE(
        jsonb_agg(entry ORDER BY (entry->>'year')::INT DESC, (entry->>'value')::NUMERIC DESC),
        '[]'::JSONB
    )
    INTO v_recent_large_list
    FROM (
        SELECT jsonb_build_object(
            'id',        id::TEXT,
            'value',     COALESCE(valor_global, 0)::NUMERIC,
            'orgao',     COALESCE(orgao_nome, ''),
            'year',      EXTRACT(YEAR FROM data_assinatura)::INT
        ) AS entry
        FROM public.pncp_supplier_contracts
        WHERE ni_fornecedor = p_cnpj
          AND is_active = TRUE
          AND valor_global > 5000000
        ORDER BY data_assinatura DESC NULLS LAST
        LIMIT p_limit
    ) sub;

    -- ═══════════════════════════════════════════════════════════════════════
    -- Signal 3: subcontracting_pattern — co-occurrence with other suppliers
    -- ═══════════════════════════════════════════════════════════════════════
    -- Detect other suppliers that co-occur in the same orgaos where this
    -- supplier has contracts.
    WITH supplier_orgaos AS (
        SELECT DISTINCT orgao_cnpj
        FROM public.pncp_supplier_contracts
        WHERE ni_fornecedor = p_cnpj
          AND is_active = TRUE
          AND orgao_cnpj IS NOT NULL
    ),
    co_occurring AS (
        SELECT
            c.ni_fornecedor,
            MAX(c.nome_fornecedor) AS nome_fornecedor,
            COUNT(*)::BIGINT AS co_occurrence_count,
            COALESCE(SUM(c.valor_global), 0)::NUMERIC AS total_value
        FROM public.pncp_supplier_contracts c
        JOIN supplier_orgaos so ON so.orgao_cnpj = c.orgao_cnpj
        WHERE c.ni_fornecedor != p_cnpj
          AND c.is_active = TRUE
          AND c.orgao_cnpj IS NOT NULL
        GROUP BY c.ni_fornecedor
        ORDER BY COUNT(*) DESC
        LIMIT p_limit
    )
    SELECT COALESCE(
        jsonb_agg(entry ORDER BY (entry->>'co_occurrence_count')::BIGINT DESC),
        '[]'::JSONB
    )
    INTO v_related_suppliers_list
    FROM (
        SELECT jsonb_build_object(
            'cnpj',                 ni_fornecedor,
            'razao_social',         COALESCE(nome_fornecedor, ''),
            'co_occurrence_count',  co_occurrence_count,
            'total_value',          total_value
        ) AS entry
        FROM co_occurring
    ) sub;

    -- Score: normalized co-occurrence ratio
    -- Higher diversity of co-occurring suppliers = higher subcontracting signal
    SELECT
        CASE
            WHEN jsonb_array_length(v_related_suppliers_list) > 0
            THEN LEAST(
                jsonb_array_length(v_related_suppliers_list)::NUMERIC / 20.0,
                1.0
            )
            ELSE 0
        END
    INTO v_subcontracting_score;

    -- ═══════════════════════════════════════════════════════════════════════
    -- Overall capacity score: weighted average
    -- ═══════════════════════════════════════════════════════════════════════
    v_overall_capacity_score := ROUND(
        (v_repeat_winner_score    * 0.3) +
        (v_large_contract_score   * 0.4) +
        (v_subcontracting_score   * 0.3),
    4);

    -- ═══════════════════════════════════════════════════════════════════════
    -- Assemble and return final payload
    -- ═══════════════════════════════════════════════════════════════════════
    RETURN jsonb_build_object(
        'cnpj',                        p_cnpj,
        'total_contracts',             v_total_contracts,
        'total_value',                 ROUND(v_total_value, 2),
        'signal_repeat_winner',        jsonb_build_object(
            'score',              ROUND(v_repeat_winner_score, 4),
            'same_orgao_count',   COALESCE(v_same_orgao_count, 0),
            'orgaos',             v_orgaos_list
        ),
        'signal_large_contract',       jsonb_build_object(
            'score',              ROUND(v_large_contract_score, 4),
            'contracts_above_5m', v_contracts_above_5m,
            'recent_large',       v_recent_large_list
        ),
        'signal_subcontracting_pattern', jsonb_build_object(
            'score',              ROUND(v_subcontracting_score, 4),
            'cnae_diversity',     jsonb_array_length(v_related_suppliers_list),
            'related_suppliers',  v_related_suppliers_list
        ),
        'overall_capacity_score',      ROUND(v_overall_capacity_score, 4)
    );
END;
$$;

COMMENT ON FUNCTION public.subcontract_capacity_signals(VARCHAR, INT) IS
    'SUBINTEL-001 (#1668) — Subcontracting Capacity Signals. Extracts repeat_winner, large_contract, and subcontracting_pattern signals from pncp_supplier_contracts. SECURITY DEFINER, service_role only.';

REVOKE ALL ON FUNCTION public.subcontract_capacity_signals(VARCHAR, INT) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.subcontract_capacity_signals(VARCHAR, INT) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.subcontract_capacity_signals(VARCHAR, INT) TO service_role;

COMMIT;
