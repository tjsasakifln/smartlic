-- ============================================================================
-- PREDINT-020: RPC get_sector_seasonal_pattern
--
-- Purpose:
--   Analyzes seasonal patterns of contract volume by month for a given
--   sector. Returns seasonal indices (monthly volume / average monthly volume)
--   to identify peak and trough months for demand forecasting.
--
-- Parameters:
--   p_setor          TEXT   -- sector identifier
--   p_uf             TEXT   -- optional UF filter
--   p_window_months  INT    -- lookback window in months (default 24)
--
-- Returns: json
--   {
--     "setor": "engenharia",
--     "uf": null,
--     "sazonalidade": [{
--       "mes_num": 1,
--       "mes_nome": "Janeiro",
--       "indice_sazonalidade": 1.25,
--       "total_contratos": 85,
--       "valor_total": 32000000.00
--     }, ...],
--     "media_mensal_contratos": 68.0,
--     "media_mensal_valor": 25600000.00
--   }
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_sector_seasonal_pattern(
    p_setor TEXT,
    p_uf TEXT DEFAULT NULL,
    p_window_months INT DEFAULT 24
) RETURNS JSON
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = 'public'
AS $$
DECLARE
    v_cutoff_date DATE;
    v_result JSON;
BEGIN
    v_cutoff_date := CURRENT_DATE - (p_window_months || ' months')::INTERVAL;

    WITH monthly_raw AS (
        SELECT
            EXTRACT(MONTH FROM data_assinatura)::INT AS mes_num,
            COUNT(*)::INT AS total_contratos,
            COALESCE(SUM(valor_global), 0)::NUMERIC(15,2) AS valor_total
        FROM pncp_supplier_contracts
        WHERE setor_classificado = p_setor
          AND data_assinatura >= v_cutoff_date
          AND (p_uf IS NULL OR p_uf = '' OR UPPER(codigo_uf) = UPPER(p_uf))
        GROUP BY EXTRACT(MONTH FROM data_assinatura)
    ),
    monthly_avg AS (
        SELECT
            AVG(total_contratos)::NUMERIC(10,2) AS media_contratos,
            AVG(valor_total)::NUMERIC(15,2) AS media_valor
        FROM monthly_raw
    )
    SELECT JSON_BUILD_OBJECT(
        'setor', p_setor,
        'uf', p_uf,
        'periodo_meses', p_window_months,
        'sazonalidade', (
            SELECT JSON_AGG(
                JSON_BUILD_OBJECT(
                    'mes_num', mr.mes_num,
                    'mes_nome', TO_CHAR(TO_DATE(mr.mes_num::TEXT, 'MM'), 'TMMonth'),
                    'indice_sazonalidade', ROUND(
                        CASE WHEN ma.media_contratos > 0
                            THEN mr.total_contratos / ma.media_contratos
                            ELSE 0 END, 2
                    ),
                    'total_contratos', mr.total_contratos,
                    'valor_total', mr.valor_total
                ) ORDER BY mr.mes_num
            )
            FROM monthly_raw mr, monthly_avg ma
        ),
        'media_mensal_contratos', (SELECT media_contratos FROM monthly_avg),
        'media_mensal_valor', (SELECT media_valor FROM monthly_avg)
    ) INTO v_result;

    RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_sector_seasonal_pattern TO service_role, anon, authenticated;

COMMENT ON FUNCTION public.get_sector_seasonal_pattern IS
  'PREDINT-020: Retorna padrao sazonal mensal de contratos por setor.';
