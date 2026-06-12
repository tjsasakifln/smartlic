-- Migration: 20260612100001_subcontract_pseo
-- Issue: #1678 — SUBINTEL-022 (EPIC-SUBINTEL #1224)
-- Purpose: Potenciais oportunidades de subcontratação para um edital aberto.
-- Source: pncp_raw_bids + pncp_supplier_contracts
--
-- RPC: get_subcontract_opportunities_for_bid
--   Input:  p_bid_id TEXT, p_setor_id TEXT DEFAULT NULL, p_limit INT DEFAULT 10
--   Output: JSON — bid details, subcontract_potential_score, reasons,
--           historical_suppliers, disclaimer

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.get_subcontract_opportunities_for_bid(
    p_bid_id TEXT,
    p_setor_id TEXT DEFAULT NULL,
    p_limit INT DEFAULT 10
)
RETURNS JSON
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_bid RECORD;
    v_total_value DECIMAL;
    v_score FLOAT := 0.0;
    v_reasons JSONB := '[]'::JSONB;
    v_suppliers JSONB := '[]'::JSONB;
    v_similar_count INT;
    v_subcontratacao_setores TEXT[] := ARRAY['engenharia', 'informatica', 'servicos_prediais', 'vigilancia', 'alimentos'];
    v_result JSON;
BEGIN
    SELECT pncp_id, objeto_compra, valor_total_estimado, uf, orgao_razao_social, orgao_cnpj
    INTO v_bid
    FROM pncp_raw_bids
    WHERE pncp_id = p_bid_id AND is_active = TRUE;

    IF v_bid.pncp_id IS NULL THEN
        RETURN json_build_object(
            'bid_id', p_bid_id,
            'error', 'Bid not found or inactive'
        );
    END IF;

    v_total_value := COALESCE(v_bid.valor_total_estimado, 0);

    -- Scoring: value > R$1M
    IF v_total_value > 1000000 THEN
        v_score := v_score + 0.3;
        v_reasons := v_reasons || jsonb_build_object(
            'reason', 'Valor acima de R$1M sugere necessidade de subcontratacao',
            'weight', 0.3
        );
    END IF;

    -- Scoring: setor com alta taxa de subcontratacao
    IF p_setor_id IS NOT NULL AND p_setor_id = ANY(v_subcontratacao_setores) THEN
        v_score := v_score + 0.2;
        v_reasons := v_reasons || jsonb_build_object(
            'reason', 'Setor de ' || p_setor_id || ' tem alta taxa de subcontratacao',
            'weight', 0.2
        );
    END IF;

    -- Scoring: orgao com historico de subcontratacao indireta
    IF v_bid.orgao_cnpj IS NOT NULL THEN
        SELECT COUNT(DISTINCT psc.ni_fornecedor)::INT INTO v_similar_count
        FROM pncp_supplier_contracts psc
        WHERE psc.orgao_cnpj = v_bid.orgao_cnpj
          AND psc.is_active = TRUE
          AND psc.ni_fornecedor IS NOT NULL;

        IF v_similar_count >= 3 THEN
            v_score := v_score + 0.3;
            v_reasons := v_reasons || jsonb_build_object(
                'reason', 'Orgao tem historico de ' || v_similar_count || ' fornecedores diferentes, sugerindo subcontratacao indireta',
                'weight', 0.3
            );
        ELSIF v_similar_count >= 1 THEN
            v_score := v_score + 0.15;
            v_reasons := v_reasons || jsonb_build_object(
                'reason', 'Orgao tem ' || v_similar_count || ' fornecedor(es) historico(s) no setor',
                'weight', 0.15
            );
        END IF;

        IF v_similar_count >= 3 THEN
            v_score := LEAST(v_score + 0.2, 1.0);
            v_reasons := v_reasons || jsonb_build_object(
                'reason', 'Ha pelo menos 3 fornecedores historicos no mesmo orgao para contratos similares',
                'weight', 0.2
            );
        END IF;
    END IF;

    v_score := LEAST(v_score, 1.0);

    -- Historical suppliers
    IF v_bid.orgao_cnpj IS NOT NULL THEN
        SELECT jsonb_agg(supplier ORDER BY supplier->>'total_value' DESC)
        INTO v_suppliers
        FROM (
            SELECT jsonb_build_object(
                'cnpj', psc.ni_fornecedor,
                'razao_social', psc.nome_fornecedor,
                'similar_contracts_count', COUNT(*)::INT,
                'total_value', COALESCE(SUM(psc.valor_global), 0),
                'avg_value', COALESCE(ROUND(AVG(psc.valor_global), 2), 0),
                'last_contract_year', EXTRACT(YEAR FROM MAX(psc.data_assinatura))::INT,
                'match_reason', 'Fornecedor historico do mesmo orgao'
            ) AS supplier
            FROM pncp_supplier_contracts psc
            WHERE psc.orgao_cnpj = v_bid.orgao_cnpj
              AND psc.is_active = TRUE
              AND psc.ni_fornecedor IS NOT NULL
            GROUP BY psc.ni_fornecedor, psc.nome_fornecedor
            ORDER BY SUM(psc.valor_global) DESC
            LIMIT p_limit
        ) supplier;
    END IF;

    v_result := json_build_object(
        'bid_id', v_bid.pncp_id,
        'bid_value', v_total_value,
        'bid_sector', COALESCE(p_setor_id, 'geral'),
        'subcontract_potential_score', ROUND(v_score::NUMERIC, 2)::FLOAT,
        'reasons', COALESCE(v_reasons, '[]'::JSONB),
        'historical_suppliers', COALESCE(v_suppliers, '[]'::JSONB),
        'disclaimer', 'Analise estimada com base em contratos publicos historicos. '
                      'A subcontratacao efetiva depende de fatores nao capturados '
                      'nesta analise (capacidade operacional, restricoes editalicias, etc).'
    );

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.get_subcontract_opportunities_for_bid(TEXT, TEXT, INT)
    IS 'SUBINTEL-022 (#1678) — Potencial de subcontratacao para edital aberto. '
       'Analisa valor, setor, historico do orgao e fornecedores similares.';

GRANT EXECUTE ON FUNCTION public.get_subcontract_opportunities_for_bid(TEXT, TEXT, INT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_subcontract_opportunities_for_bid(TEXT, TEXT, INT) TO service_role;
