-- Migration: subcontract_partnership_score
-- Purpose: Score 0-100 de probabilidade de parceria/subcontratação com um
--           fornecedor. Analisa: volume de contratos, concentração geográfica,
--           diversidade de órgãos, recorrência, e tamanho relativo.
-- Epic: EPIC-SUBINTEL (#1224) — SUBINTEL-011 (Score de Oportunidade de Parceria)
-- Source: pncp_supplier_contracts

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.subcontract_partnership_score(
    p_cnpj TEXT
)
RETURNS TABLE(
    score INT,
    factors JSONB,
    similar_suppliers JSONB,
    recommended_actions JSONB
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cnpj_clean TEXT;
    v_total_contratos INT;
    v_total_orgaos INT;
    v_total_ufs INT;
    v_avg_ticket NUMERIC;
    v_hhi NUMERIC;  -- Herfindahl-Hirschman Index (concentração de órgãos)
    v_recent_trend TEXT;
    v_score INT := 0;
BEGIN
    -- Sanitize CNPJ
    v_cnpj_clean := regexp_replace(p_cnpj, '[^0-9]', '', 'g');
    IF length(v_cnpj_clean) <> 14 THEN
        RAISE EXCEPTION 'CNPJ inválido: deve ter 14 dígitos', p_cnpj
            USING ERRCODE = '22000';
    END IF;

    -- Gather supplier stats
    SELECT
        COUNT(*)::INT,
        COUNT(DISTINCT psc.orgao_cnpj)::INT,
        COUNT(DISTINCT psc.uf)::INT,
        COALESCE(AVG(psc.valor_global), 0)
    INTO
        v_total_contratos, v_total_orgaos, v_total_ufs, v_avg_ticket
    FROM pncp_supplier_contracts psc
    WHERE psc.ni_fornecedor = v_cnpj_clean AND psc.is_active = TRUE;

    -- No data: return zero score
    IF v_total_contratos = 0 THEN
        RETURN QUERY SELECT
            0::INT,
            '{"error": "Fornecedor sem contratos no período"}'::JSONB,
            '[]'::JSONB,
            '[]'::JSONB;
        RETURN;
    END IF;

    -- Calculate HHI (market concentration across órgãos)
    SELECT COALESCE(SUM((org_share * 100) ^ 2), 0)
    INTO v_hhi
    FROM (
        SELECT COUNT(*)::NUMERIC / NULLIF(v_total_contratos, 0) AS org_share
        FROM pncp_supplier_contracts psc
        WHERE psc.ni_fornecedor = v_cnpj_clean AND psc.is_active = TRUE
        GROUP BY psc.orgao_cnpj
    ) shares;

    -- Determine recent trend (últimos 12 meses vs. 12-24 meses atrás)
    SELECT
        CASE
            WHEN recent.cnt > older.cnt * 1.2 THEN 'crescendo'
            WHEN recent.cnt < older.cnt * 0.8 THEN 'diminuindo'
            ELSE 'estavel'
        END
    INTO v_recent_trend
    FROM (
        SELECT COUNT(*)::NUMERIC AS cnt
        FROM pncp_supplier_contracts psc
        WHERE psc.ni_fornecedor = v_cnpj_clean
          AND psc.is_active = TRUE
          AND psc.data_assinatura >= CURRENT_DATE - INTERVAL '12 months'
    ) recent,
    (
        SELECT COUNT(*)::NUMERIC AS cnt
        FROM pncp_supplier_contracts psc
        WHERE psc.ni_fornecedor = v_cnpj_clean
          AND psc.is_active = TRUE
          AND psc.data_assinatura >= CURRENT_DATE - INTERVAL '24 months'
          AND psc.data_assinatura < CURRENT_DATE - INTERVAL '12 months'
    ) older;

    -- Score calculation (0-100)
    -- Factor 1: Volume (0-25 pts) — mais contratos = mais oportunidade de parceria
    v_score := v_score + LEAST(25, v_total_contratos);
    -- Factor 2: Diversidade geográfica (0-25 pts) — multi-UF = mais pontes
    v_score := v_score + LEAST(25, v_total_ufs * 5);
    -- Factor 3: Diversidade de órgãos (0-25 pts) — multi-órgão = mais entradas
    v_score := v_score + LEAST(25, v_total_orgaos * 3);
    -- Factor 4: Baixa concentração (0-15 pts) — HHI < 2500 = não dependente de 1 órgão
    v_score := v_score + CASE WHEN v_hhi < 1000 THEN 15
                               WHEN v_hhi < 2500 THEN 10
                               WHEN v_hhi < 5000 THEN 5
                               ELSE 0 END;
    -- Factor 5: Tendência (0-10 pts)
    v_score := v_score + CASE WHEN v_recent_trend = 'crescendo' THEN 10
                               WHEN v_recent_trend = 'estavel' THEN 5
                               ELSE 0 END;
    -- Cap at 100
    v_score := LEAST(100, v_score);

    -- Find similar suppliers (mesmo setor geográfico, mesmo porte)
    RETURN QUERY
    WITH similar AS (
        SELECT
            psc2.ni_fornecedor AS supplier_cnpj,
            psc2.nome_fornecedor AS supplier_name,
            COUNT(*)::INT AS contract_count,
            COUNT(DISTINCT psc2.uf)::INT AS uf_count
        FROM pncp_supplier_contracts psc2
        WHERE psc2.is_active = TRUE
          AND psc2.ni_fornecedor <> v_cnpj_clean
          AND psc2.uf IN (
              SELECT DISTINCT psc3.uf
              FROM pncp_supplier_contracts psc3
              WHERE psc3.ni_fornecedor = v_cnpj_clean AND psc3.is_active = TRUE
          )
        GROUP BY psc2.ni_fornecedor, psc2.nome_fornecedor
        HAVING COUNT(*) >= 3
        ORDER BY COUNT(*) DESC
        LIMIT 5
    ),
    actions AS (
        SELECT jsonb_agg(jsonb_build_object(
            'action', action_text,
            'priority', priority
        )) AS recommended_actions
        FROM (
            SELECT
                'Abordar para parceria em ' || string_agg(DISTINCT psc4.uf, ', ') AS action_text,
                'alta' AS priority
            FROM pncp_supplier_contracts psc4
            WHERE psc4.ni_fornecedor = v_cnpj_clean AND psc4.is_active = TRUE
            HAVING COUNT(*) >= 5
        ) acts
    )
    SELECT
        v_score,
        jsonb_build_object(
            'total_contratos', v_total_contratos,
            'total_orgaos', v_total_orgaos,
            'total_ufs', v_total_ufs,
            'avg_ticket', v_avg_ticket,
            'hhi_concentracao', ROUND(v_hhi, 1),
            'tendencia_recente', v_recent_trend
        ) AS factors,
        COALESCE((
            SELECT jsonb_agg(jsonb_build_object(
                'cnpj', s.supplier_cnpj,
                'nome', s.supplier_name,
                'contratos', s.contract_count,
                'ufs', s.uf_count
            ))
            FROM similar s
        ), '[]'::JSONB) AS similar_suppliers,
        COALESCE((
            SELECT a.recommended_actions FROM actions a
        ), '[]'::JSONB) AS recommended_actions;
END;
$$;

COMMENT ON FUNCTION public.subcontract_partnership_score(TEXT)
    IS 'Score 0-100 de probabilidade de parceria com fornecedor. '
       '5 fatores: volume, diversidade geográfica, diversidade órgãos, '
       'concentração (HHI), tendência. Epic: SUBINTEL (#1224).';
