-- ============================================================================
-- PREDINT-020: RPC get_uf_demand_trend
--
-- Purpose:
--   Analyzes demand trends by UF for a given sector, comparing recent
--   contract activity (last 3 months) against the prior period to detect
--   growth, decline, or stable demand.
--
-- Parameters:
--   p_setor          TEXT   -- sector identifier
--   p_window_months  INT    -- lookback window in months (default 12)
--
-- Returns: json
--   {
--     "setor": "engenharia",
--     "tendencias": [{
--       "uf": "SP",
--       "total_contratos": 120,
--       "valor_total": 45000000.00,
--       "variacao_percentual": 15.5,
--       "tendencia": "crescimento",
--       "contratos_recentes": 45,
--       "contratos_anteriores": 35
--     }, ...]
--   }
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_uf_demand_trend(
    p_setor TEXT,
    p_window_months INT DEFAULT 12
) RETURNS JSON
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = 'public'
AS $$
DECLARE
    v_cutoff_date DATE;
    v_midpoint_date DATE;
    v_result JSON;
BEGIN
    v_cutoff_date := CURRENT_DATE - (p_window_months || ' months')::INTERVAL;
    v_midpoint_date := CURRENT_DATE - ((p_window_months / 2) || ' months')::INTERVAL;

    WITH uf_data AS (
        SELECT
            UPPER(codigo_uf) AS uf,
            COUNT(*)::INT AS total_contratos,
            COALESCE(SUM(valor_global), 0)::NUMERIC(15,2) AS valor_total,
            COUNT(*) FILTER (WHERE data_assinatura >= v_midpoint_date)::INT AS contratos_recentes,
            COUNT(*) FILTER (WHERE data_assinatura < v_midpoint_date)::INT AS contratos_anteriores
        FROM pncp_supplier_contracts
        WHERE setor_classificado = p_setor
          AND data_assinatura >= v_cutoff_date
          AND codigo_uf IS NOT NULL
          AND codigo_uf != ''
        GROUP BY UPPER(codigo_uf)
    )
    SELECT JSON_BUILD_OBJECT(
        'setor', p_setor,
        'periodo_meses', p_window_months,
        'tendencias', (
            SELECT JSON_AGG(
                JSON_BUILD_OBJECT(
                    'uf', uf,
                    'total_contratos', total_contratos,
                    'valor_total', valor_total,
                    'variacao_percentual', CASE
                        WHEN contratos_anteriores > 0
                        THEN ROUND(
                            (contratos_recentes::NUMERIC - contratos_anteriores::NUMERIC)
                            / contratos_anteriores::NUMERIC * 100, 1)
                        ELSE NULL END,
                    'tendencia', CASE
                        WHEN contratos_anteriores = 0 THEN 'nova'
                        WHEN contratos_recentes > contratos_anteriores * 1.2 THEN 'crescimento'
                        WHEN contratos_recentes < contratos_anteriores * 0.8 THEN 'declinio'
                        ELSE 'estavel' END,
                    'contratos_recentes', contratos_recentes,
                    'contratos_anteriores', contratos_anteriores
                ) ORDER BY total_contratos DESC
            )
            FROM uf_data
        )
    ) INTO v_result;

    RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_uf_demand_trend TO service_role, anon, authenticated;

COMMENT ON FUNCTION public.get_uf_demand_trend IS
  'PREDINT-020: Retorna tendencia de demanda por UF para um setor.';
