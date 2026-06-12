-- ============================================================================
-- PREDINT-020: RPC get_sector_monthly_volume
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_sector_monthly_volume(
    p_setor TEXT,
    p_uf TEXT DEFAULT NULL,
    p_window_months INT DEFAULT 12
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

    WITH monthly_data AS (
        SELECT
            TO_CHAR(data_assinatura, 'YYYY-MM') AS mes,
            COUNT(*)::INT AS total_contratos,
            COALESCE(SUM(valor_global), 0)::NUMERIC(15,2) AS valor_total
        FROM pncp_supplier_contracts
        WHERE setor_classificado = p_setor
          AND data_assinatura >= v_cutoff_date
          AND (p_uf IS NULL OR p_uf = '' OR UPPER(codigo_uf) = UPPER(p_uf))
        GROUP BY TO_CHAR(data_assinatura, 'YYYY-MM')
        ORDER BY mes
    ),
    totals AS (
        SELECT
            COALESCE(SUM(total_contratos), 0)::INT AS total_geral,
            COALESCE(SUM(valor_total), 0)::NUMERIC(15,2) AS valor_geral,
            GREATEST(COUNT(*), 1)::INT AS num_meses
        FROM monthly_data
    )
    SELECT JSON_BUILD_OBJECT(
        'setor', p_setor,
        'uf', p_uf,
        'periodo_meses', p_window_months,
        'serie', (SELECT JSON_AGG(
            JSON_BUILD_OBJECT(
                'mes', md.mes,
                'total_contratos', md.total_contratos,
                'valor_total', md.valor_total,
                'media_valor', CASE WHEN md.total_contratos > 0
                    THEN ROUND(md.valor_total / md.total_contratos, 2)
                    ELSE 0 END
            )
        ) FROM monthly_data md),
        'total_contratos', t.total_geral,
        'valor_total_geral', t.valor_geral,
        'media_mensal_valor', ROUND(t.valor_geral / t.num_meses, 2)
    ) INTO v_result
    FROM totals t;

    RETURN v_result;
END;
$$;

GRANT EXECUTE ON FUNCTION public.get_sector_monthly_volume TO service_role, anon, authenticated;

COMMENT ON FUNCTION public.get_sector_monthly_volume IS
  'PREDINT-020: Retorna volume mensal de contratos por setor, agregado por mes.';
