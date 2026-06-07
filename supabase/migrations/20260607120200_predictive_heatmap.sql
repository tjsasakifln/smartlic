-- Migration: predictive_heatmap
-- Purpose: Matriz UF × mês com intensidade preditiva de oportunidades.
--           Combina recorrência histórica + volume para gerar heatmap nacional.
-- Epic: EPIC-PREDINT (#1260) — PREDINT-011 (Heatmap Nacional)
-- Source: pncp_supplier_contracts
-- Intensidade: 0-100 baseado em recorrência + volume relativo

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.predictive_heatmap(
    p_setor TEXT DEFAULT NULL
)
RETURNS TABLE(
    uf_sigla TEXT,
    mes INT,
    intensidade INT,
    total_previsto NUMERIC,
    confianca_media FLOAT
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cutoff_date DATE := CURRENT_DATE - INTERVAL '3 years';
    v_max_total NUMERIC;
BEGIN
    RETURN QUERY
    WITH monthly_aggregates AS (
        SELECT
            psc.uf AS uf_sigla,
            EXTRACT(MONTH FROM psc.data_assinatura)::INT AS mes,
            COUNT(*)::INT AS contract_count,
            COALESCE(AVG(psc.valor_global), 0) AS total_previsto,
            -- Confidence based on data consistency across years
            CASE
                WHEN COUNT(DISTINCT EXTRACT(YEAR FROM psc.data_assinatura)) >= 3
                    THEN 80.0
                WHEN COUNT(DISTINCT EXTRACT(YEAR FROM psc.data_assinatura)) = 2
                    THEN 60.0
                ELSE 40.0
            END AS confianca_media
        FROM pncp_supplier_contracts psc
        WHERE psc.is_active = TRUE
          AND psc.data_assinatura >= v_cutoff_date
          AND psc.valor_global > 0
          AND psc.uf IS NOT NULL
          AND psc.uf IN (
              'AC','AL','AM','AP','BA','CE','DF','ES','GO',
              'MA','MG','MS','MT','PA','PB','PE','PI','PR',
              'RJ','RN','RO','RR','RS','SC','SE','SP','TO'
          )
        GROUP BY psc.uf, EXTRACT(MONTH FROM psc.data_assinatura)::INT
        HAVING COUNT(*) >= 3
    )
    SELECT
        ma.uf_sigla,
        ma.mes,
        -- Intensity: normalize contract count as percentile within UF
        LEAST(100, GREATEST(0, ROUND(
            (ma.contract_count::NUMERIC /
             NULLIF(MAX(ma.contract_count) OVER (PARTITION BY ma.uf_sigla), 0)) * 100
        )))::INT AS intensidade,
        ma.total_previsto,
        ma.confianca_media
    FROM monthly_aggregates ma
    ORDER BY ma.uf_sigla, ma.intensidade DESC
    LIMIT 500;
END;
$$;

COMMENT ON FUNCTION public.predictive_heatmap(TEXT)
    IS 'Matriz UF × mês com intensidade preditiva de oportunidades futuras. '
       'Intensidade 0-100 baseada em recorrência e volume. Epic: PREDINT (#1260).';
