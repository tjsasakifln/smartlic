-- Migration: predictive_recorrencia
-- Purpose: Analisa séries temporais de contratos para prever recorrência de editais.
--           Mesmo órgão + mesmo objeto + intervalo regular nos últimos 3 anos.
-- Epic: EPIC-PREDINT (#1260) — PREDINT-010, PREDINT-013
-- Source: pncp_supplier_contracts
--
-- Confidence = 1 - (stddev do intervalo / média do intervalo), capped 0-100.
-- Confidence >= 70 = alta previsibilidade, 40-69 = média, <40 = baixa.

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.predictive_recorrencia(
    p_setor TEXT DEFAULT NULL,
    p_uf TEXT DEFAULT NULL,
    p_meses_projecao INT DEFAULT 6
)
RETURNS TABLE(
    orgao_nome TEXT,
    objeto_previsto TEXT,
    mes_estimado DATE,
    valor_estimado NUMERIC,
    confidence FLOAT,
    historico_contratos INT,
    ultimo_contrato DATE
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cutoff_date DATE := CURRENT_DATE - INTERVAL '3 years';
BEGIN
    -- Sanitize inputs
    p_uf := upper(trim(p_uf));
    IF p_meses_projecao < 1 OR p_meses_projecao > 24 THEN
        p_meses_projecao := 6;
    END IF;

    RETURN QUERY
    WITH contratos_filtrados AS (
        SELECT
            psc.orgao_nome,
            psc.objeto_contrato,
            psc.data_assinatura,
            psc.valor_global,
            psc.uf
        FROM pncp_supplier_contracts psc
        WHERE psc.is_active = TRUE
          AND psc.data_assinatura >= v_cutoff_date
          AND psc.valor_global > 0
          AND psc.orgao_nome IS NOT NULL
          AND psc.objeto_contrato IS NOT NULL
    ),
    recorrencias AS (
        SELECT
            cf.orgao_nome,
            cf.objeto_contrato AS objeto_previsto,
            COUNT(*)::INT AS historico_contratos,
            MAX(cf.data_assinatura) AS ultimo_contrato,
            AVG(cf.valor_global) AS valor_estimado,
            -- Calculate regularity: stddev of intervals / mean of intervals
            CASE
                WHEN COUNT(*) >= 3 THEN
                    GREATEST(0, LEAST(100, ROUND(
                        (1 - (STDDEV(
                            EXTRACT(EPOCH FROM (cf.data_assinatura - LAG(cf.data_assinatura)
                                OVER (PARTITION BY cf.orgao_nome, cf.objeto_contrato
                                      ORDER BY cf.data_assinatura)))
                        ) / NULLIF(AVG(
                            EXTRACT(EPOCH FROM (cf.data_assinatura - LAG(cf.data_assinatura)
                                OVER (PARTITION BY cf.orgao_nome, cf.objeto_contrato
                                      ORDER BY cf.data_assinatura)))
                        ), 0))) * 100
                    )::FLOAT)
                WHEN COUNT(*) = 2 THEN 40.0  -- 2 data points: low confidence
                ELSE 20.0                     -- 1 data point: very low confidence
            END AS confidence
        FROM contratos_filtrados cf
        GROUP BY cf.orgao_nome, cf.objeto_contrato
        HAVING COUNT(*) >= 1
    ),
    projecoes AS (
        SELECT
            r.*,
            -- Estimate next occurrence based on average interval
            (r.ultimo_contrato + (
                (r.ultimo_contrato - LAG(r.ultimo_contrato)
                    OVER (PARTITION BY r.orgao_nome ORDER BY r.ultimo_contrato DESC))
                / NULLIF(r.historico_contratos - 1, 0)
            ) * INTERVAL '1 day')::DATE AS mes_estimado_raw
        FROM recorrencias r
    )
    SELECT
        p.orgao_nome,
        p.objeto_previsto,
        p.mes_estimado_raw AS mes_estimado,
        p.valor_estimado,
        p.confidence,
        p.historico_contratos,
        p.ultimo_contrato
    FROM projecoes p
    WHERE p.confidence >= 30  -- Filter out unreliable predictions
      AND p.mes_estimado_raw BETWEEN CURRENT_DATE
          AND (CURRENT_DATE + (p_meses_projecao || ' months')::INTERVAL)
    ORDER BY p.confidence DESC, p.valor_estimado DESC
    LIMIT 100;
END;
$$;

COMMENT ON FUNCTION public.predictive_recorrencia(TEXT, TEXT, INT)
    IS 'Prevê recorrência de editais baseado em séries temporais de contratos. '
       'Confidence: >=70 alta previsibilidade, 40-69 média, <40 baixa. '
       'Fonte: pncp_supplier_contracts. Epic: PREDINT (#1260).';
