-- SUBINTEL-001 (Wave 0): RPC subcontract_capacity_signals
--
-- Derives, by supplier CNPJ, signals of presumed operational capacity vs.
-- contracted load from pncp_supplier_contracts (~2-4M rows).
--
-- Base for Subcontract Score (SUBINTEL-010). Returns scalar JSON
-- (DATA-CAP-001 pattern) to bypass PostgREST max-rows=1000.
--
-- Core insight: a company that won many simultaneous contracts, across many
-- UFs, with high aggregated value in a short window has high probability of
-- needing to outsource/subcontract.
--
-- Expected p95 < 800ms using existing indexes:
--   idx_psc_ni_fornecedor (ni_fornecedor)
--   idx_psc_fornecedor_data (ni_fornecedor, data_assinatura DESC)

CREATE OR REPLACE FUNCTION public.subcontract_capacity_signals(
    p_ni_fornecedor TEXT,
    p_window_months INT DEFAULT 24
)
RETURNS json
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_cutoff           DATE;
    v_total            INT;
    v_valor_total      NUMERIC(18,2);
    v_ticket_medio     NUMERIC(18,2);
    v_contratos_pico   INT;
    v_ufs              INT;
    v_municipios       INT;
    v_orgaos           INT;
    v_uf_ratio         NUMERIC;
    v_score            NUMERIC;
    v_valor_por_uf     json;
    v_contratos_ano    json;
BEGIN
    v_cutoff := CURRENT_DATE - (p_window_months || ' months')::interval;

    -- Base aggregates: count, sum, avg, distinct UFs/municipios/orgaos
    SELECT
        COUNT(*),
        COALESCE(SUM(valor_global), 0),
        COALESCE(AVG(valor_global), 0),
        COUNT(DISTINCT uf),
        COUNT(DISTINCT municipio),
        COUNT(DISTINCT orgao_nome)
    INTO
        v_total, v_valor_total, v_ticket_medio,
        v_ufs, v_municipios, v_orgaos
    FROM pncp_supplier_contracts
    WHERE ni_fornecedor = p_ni_fornecedor
      AND is_active = true
      AND data_assinatura >= v_cutoff;

    -- Max number of contracts with overlapping data_assinatura
    -- in 12-month forward windows (self-join on date ranges)
    SELECT COALESCE(MAX(s.cnt), 0) INTO v_contratos_pico
    FROM (
        SELECT COUNT(*) AS cnt
        FROM pncp_supplier_contracts a
        JOIN pncp_supplier_contracts b
            ON b.ni_fornecedor = a.ni_fornecedor
            AND b.is_active = true
            AND b.data_assinatura >= a.data_assinatura
            AND b.data_assinatura < a.data_assinatura + INTERVAL '12 months'
        WHERE a.ni_fornecedor = p_ni_fornecedor
            AND a.is_active = true
            AND a.data_assinatura >= v_cutoff
        GROUP BY a.id
    ) s;

    -- valor_por_uf: aggregate contracts by UF
    SELECT COALESCE(json_agg(
        json_build_object(
            'uf', uf,
            'contratos', cnt,
            'valor', vlr
        ) ORDER BY cnt DESC
    ), '[]'::json) INTO v_valor_por_uf
    FROM (
        SELECT uf, COUNT(*)::int AS cnt, SUM(valor_global) AS vlr
        FROM pncp_supplier_contracts
        WHERE ni_fornecedor = p_ni_fornecedor
            AND is_active = true
            AND data_assinatura >= v_cutoff
        GROUP BY uf
    ) t;

    -- contratos_por_ano: aggregate contracts by year
    SELECT COALESCE(json_agg(
        json_build_object(
            'ano', ano,
            'contratos', cnt,
            'valor', vlr
        ) ORDER BY ano
    ), '[]'::json) INTO v_contratos_ano
    FROM (
        SELECT EXTRACT(YEAR FROM data_assinatura)::int AS ano,
               COUNT(*)::int AS cnt,
               SUM(valor_global) AS vlr
        FROM pncp_supplier_contracts
        WHERE ni_fornecedor = p_ni_fornecedor
            AND is_active = true
            AND data_assinatura >= v_cutoff
        GROUP BY EXTRACT(YEAR FROM data_assinatura)
    ) t;

    -- Composite score_capacidade (0-1): higher = more likely to subcontract
    -- Factors:
    --   30% UF diversity (ufs_distintas / total_contratos ratio -- spread risk)
    --   40% Contract overlap (contratos_simultaneos_pico -- concurrent load)
    --   30% Ticket concentration (ticket_medio -- financial exposure)
    v_uf_ratio := CASE WHEN v_total > 0 THEN v_ufs::numeric / v_total ELSE 0 END;
    v_score := LEAST(1.0,
        0.3 * LEAST(1.0, v_uf_ratio * 5) +
        0.4 * LEAST(1.0, v_contratos_pico::numeric / 20.0) +
        0.3 * LEAST(1.0, COALESCE(v_ticket_medio, 0) / 5000000.0)
    );
    v_score := ROUND(v_score, 2);

    RETURN json_build_object(
        'ni_fornecedor', p_ni_fornecedor,
        'total_contratos', v_total,
        'valor_total', v_valor_total,
        'ticket_medio', ROUND(COALESCE(v_ticket_medio, 0), 2),
        'contratos_simultaneos_pico', v_contratos_pico,
        'ufs_distintas', v_ufs,
        'municipios_distintos', v_municipios,
        'orgaos_distintos', v_orgaos,
        'valor_por_uf', v_valor_por_uf,
        'contratos_por_ano', v_contratos_ano,
        'score_capacidade', v_score,
        'sinal_sobrecarga', v_score > 0.6
    );
END;
$$;

COMMENT ON FUNCTION public.subcontract_capacity_signals(TEXT, INT)
    IS 'SUBINTEL-001: Derives subcontract capacity signals for a supplier CNPJ. '
       'Returns JSON with contract aggregates, overlap metrics, and a composite score_capacidade.';

GRANT EXECUTE ON FUNCTION public.subcontract_capacity_signals(TEXT, INT) TO anon;
GRANT EXECUTE ON FUNCTION public.subcontract_capacity_signals(TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.subcontract_capacity_signals(TEXT, INT) TO service_role;
