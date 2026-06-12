-- ============================================================================
-- UP: widget_competitive_intel_rpc — Aggregation for Competitive Intel Widget
-- Date: 2026-06-11
-- Issue: #1619
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   WIDGET-COMPINT-001: Embeddable widget showing "Market Share de [Setor] em
--   Contratos Públicos" with real data from pncp_supplier_contracts. Used by
--   frontend iframe pages and external sites.
--
--   This RPC returns a JSONB payload with data for all 4 widget themes:
--     market-share, top-winners, monthly-trend, orgao-ranking
--
--   When p_uf is provided, filters to that UF; otherwise aggregates nationally.
--   Keywords are used to match sector via objeto_contrato ILIKE.
--
--   SECURITY DEFINER + SET search_path = public, pg_temp is mandatory per
--   SEC-SECDEF-001/002 (feedback_secdef_search_path_trap).
--   GRANT to service_role only — accessed via backend admin client.
-- ============================================================================

BEGIN;

CREATE OR REPLACE FUNCTION public.widget_competitive_intel(
    p_sector         TEXT,
    p_keywords       TEXT[],
    p_uf             TEXT DEFAULT NULL,
    p_window_months  INTEGER DEFAULT 12
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_uf_clean       TEXT;
    v_window_start   DATE;
    v_result         JSONB;

    -- Headline
    v_total_count        BIGINT;
    v_total_value        NUMERIC;

    -- Market share
    v_top_fornecedores   JSONB;

    -- Monthly trend
    v_serie_temporal     JSONB;

    -- Orgao ranking
    v_top_orgaos         JSONB;
BEGIN
    -- Defesa em profundidade: timeout local de 15s
    SET LOCAL statement_timeout = '15s';

    -- Validar inputs
    IF p_keywords IS NULL OR array_length(p_keywords, 1) IS NULL THEN
        RAISE EXCEPTION 'p_keywords must be a non-empty array';
    END IF;

    IF p_uf IS NOT NULL AND p_uf <> '' THEN
        v_uf_clean := upper(regexp_replace(p_uf, '[^A-Za-z]', '', 'g'));
        IF length(v_uf_clean) <> 2 THEN
            RAISE EXCEPTION 'invalid uf: must be 2-letter state code after normalization';
        END IF;
    ELSE
        v_uf_clean := NULL;
    END IF;

    IF p_window_months IS NULL OR p_window_months < 1 OR p_window_months > 240 THEN
        RAISE EXCEPTION 'invalid window: p_window_months must be between 1 and 240';
    END IF;

    v_window_start := (CURRENT_DATE - (p_window_months || ' months')::INTERVAL)::DATE;

    -- ── Headline metrics (single pass)
    EXECUTE format(
        'SELECT
            COUNT(*)::BIGINT,
            COALESCE(SUM(valor_global), 0)::NUMERIC
          FROM public.pncp_supplier_contracts
         WHERE is_active = TRUE
           AND data_assinatura >= $1
           AND EXISTS (
               SELECT 1 FROM unnest($2) AS kw
                WHERE objeto_contrato ILIKE ''%%'' || kw || ''%%''
           )
           %s',
        CASE WHEN v_uf_clean IS NOT NULL THEN 'AND upper(uf) = $3' ELSE '' END
    )
    INTO v_total_count, v_total_value
    USING v_window_start, p_keywords,
          CASE WHEN v_uf_clean IS NOT NULL THEN v_uf_clean ELSE NULL END;

    -- ── Top 20 fornecedores (market-share + top-winners)
    EXECUTE format(
        'SELECT COALESCE(
            jsonb_agg(entry ORDER BY (entry->>''valor_total'')::NUMERIC DESC),
            ''[]''::JSONB
          )
          FROM (
            SELECT jsonb_build_object(
                       ''ni_fornecedor'',   ni_fornecedor,
                       ''nome_fornecedor'', MAX(nome_fornecedor),
                       ''count'',           COUNT(*)::BIGINT,
                       ''valor_total'',     COALESCE(SUM(valor_global), 0)::NUMERIC,
                       ''avg_ticket'',      COALESCE(AVG(valor_global), 0)::NUMERIC
                   ) AS entry
              FROM public.pncp_supplier_contracts
             WHERE is_active = TRUE
               AND data_assinatura >= $1
               AND EXISTS (
                   SELECT 1 FROM unnest($2) AS kw
                    WHERE objeto_contrato ILIKE ''%%'' || kw || ''%%''
               )
               AND ni_fornecedor IS NOT NULL
               %s
             GROUP BY ni_fornecedor
             ORDER BY SUM(valor_global) DESC NULLS LAST
             LIMIT 20
          ) sub',
        CASE WHEN v_uf_clean IS NOT NULL THEN 'AND upper(uf) = $3' ELSE '' END
    )
    INTO v_top_fornecedores
    USING v_window_start, p_keywords,
          CASE WHEN v_uf_clean IS NOT NULL THEN v_uf_clean ELSE NULL END;

    -- ── Série temporal mensal com zero-fill via generate_series
    EXECUTE format(
        'SELECT COALESCE(jsonb_agg(entry ORDER BY entry->>''mes''), ''[]''::JSONB)
          FROM (
            SELECT jsonb_build_object(
                       ''mes'',         to_char(gs.mes, ''YYYY-MM''),
                       ''count'',       COALESCE(agg.cnt, 0)::BIGINT,
                       ''valor_total'', COALESCE(agg.valor, 0)::NUMERIC
                   ) AS entry
              FROM (
                SELECT generate_series(
                           date_trunc(''month'', $1::TIMESTAMP),
                           date_trunc(''month'', CURRENT_DATE::TIMESTAMP),
                           ''1 month''::INTERVAL
                       ) AS mes
              ) gs
              LEFT JOIN (
                SELECT date_trunc(''month'', data_assinatura) AS mes,
                       COUNT(*)::BIGINT AS cnt,
                       COALESCE(SUM(valor_global), 0)::NUMERIC AS valor
                  FROM public.pncp_supplier_contracts
                 WHERE is_active = TRUE
                   AND data_assinatura >= $1
                   AND EXISTS (
                       SELECT 1 FROM unnest($2) AS kw
                        WHERE objeto_contrato ILIKE ''%%'' || kw || ''%%''
                   )
                   AND data_assinatura IS NOT NULL
                   %s
                 GROUP BY date_trunc(''month'', data_assinatura)
              ) agg ON agg.mes = gs.mes
          ) t',
        CASE WHEN v_uf_clean IS NOT NULL THEN 'AND upper(uf) = $3' ELSE '' END
    )
    INTO v_serie_temporal
    USING v_window_start, p_keywords,
          CASE WHEN v_uf_clean IS NOT NULL THEN v_uf_clean ELSE NULL END;

    -- ── Top 10 órgãos compradores (orgao-ranking)
    EXECUTE format(
        'SELECT COALESCE(
            jsonb_agg(entry ORDER BY (entry->>''valor_total'')::NUMERIC DESC),
            ''[]''::JSONB
          )
          FROM (
            SELECT jsonb_build_object(
                       ''orgao_cnpj'',  orgao_cnpj,
                       ''orgao_nome'',  MAX(orgao_nome),
                       ''count'',       COUNT(*)::BIGINT,
                       ''valor_total'', COALESCE(SUM(valor_global), 0)::NUMERIC
                   ) AS entry
              FROM public.pncp_supplier_contracts
             WHERE is_active = TRUE
               AND data_assinatura >= $1
               AND EXISTS (
                   SELECT 1 FROM unnest($2) AS kw
                    WHERE objeto_contrato ILIKE ''%%'' || kw || ''%%''
               )
               AND orgao_cnpj IS NOT NULL
               %s
             GROUP BY orgao_cnpj
             ORDER BY SUM(valor_global) DESC NULLS LAST
             LIMIT 10
          ) sub',
        CASE WHEN v_uf_clean IS NOT NULL THEN 'AND upper(uf) = $3' ELSE '' END
    )
    INTO v_top_orgaos
    USING v_window_start, p_keywords,
          CASE WHEN v_uf_clean IS NOT NULL THEN v_uf_clean ELSE NULL END;

    -- ── Assemble final payload
    v_result := jsonb_build_object(
        'sector',           COALESCE(p_sector, ''),
        'uf',               v_uf_clean,
        'window_months',    p_window_months,
        'window_start',     to_char(v_window_start, 'YYYY-MM-DD'),
        'generated_at',     to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
        'total_contracts',  v_total_count,
        'total_value',      v_total_value,
        'top_fornecedores', v_top_fornecedores,
        'serie_temporal',   v_serie_temporal,
        'top_orgaos',       v_top_orgaos
    );

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.widget_competitive_intel(TEXT, TEXT[], TEXT, INTEGER) IS
    'WIDGET-COMPINT-001 — Agregações para widget de Inteligência Competitiva. SECURITY DEFINER, service_role only.';

REVOKE ALL ON FUNCTION public.widget_competitive_intel(TEXT, TEXT[], TEXT, INTEGER) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.widget_competitive_intel(TEXT, TEXT[], TEXT, INTEGER) FROM anon, authenticated;
GRANT EXECUTE ON FUNCTION public.widget_competitive_intel(TEXT, TEXT[], TEXT, INTEGER) TO service_role;

COMMIT;
