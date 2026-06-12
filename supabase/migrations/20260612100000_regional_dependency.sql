-- Migration: 20260612100000_regional_dependency
-- Issue: #1681 — SUBINTEL-012 (EPIC-SUBINTEL #1224)
-- Purpose: Indice de Dependencia Regional por setor — distribuição geográfica
--          de contratos por UF, score de dependência (share %).
-- Source: pncp_supplier_contracts
--
-- RPC: get_regional_dependency_index
--   Input:  p_setor_id TEXT, p_keywords TEXT[] DEFAULT NULL
--   Output: TABLE(uf TEXT, dependency_score FLOAT, contract_count INT, total_value DECIMAL)
--
--   Se p_keywords for fornecido, filtra por correspondência textual
--   no objeto_contrato. Se NULL, retorna distribuição geral.

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.get_regional_dependency_index(
    p_setor_id TEXT,
    p_keywords TEXT[] DEFAULT NULL
)
RETURNS TABLE(
    uf TEXT,
    dependency_score FLOAT,
    contract_count INT,
    total_value DECIMAL
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_total_contratos INT;
    v_total_valor DECIMAL;
BEGIN
    -- Total contracts (for normalization)
    IF p_keywords IS NOT NULL AND array_length(p_keywords, 1) > 0 THEN
        SELECT COUNT(*)::INT, COALESCE(SUM(valor_global), 0)
        INTO v_total_contratos, v_total_valor
        FROM pncp_supplier_contracts psc
        WHERE psc.is_active = TRUE
          AND psc.uf IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM unnest(p_keywords) kw
              WHERE position(lower(kw) IN lower(psc.objeto_contrato)) > 0
          );
    ELSE
        SELECT COUNT(*)::INT, COALESCE(SUM(valor_global), 0)
        INTO v_total_contratos, v_total_valor
        FROM pncp_supplier_contracts psc
        WHERE psc.is_active = TRUE
          AND psc.uf IS NOT NULL;
    END IF;

    IF v_total_contratos = 0 THEN
        RETURN;
    END IF;

    RETURN QUERY
    WITH uf_stats AS (
        SELECT
            psc.uf AS uf_sigla,
            COUNT(*)::INT AS contract_count,
            COALESCE(SUM(psc.valor_global), 0) AS total_value
        FROM pncp_supplier_contracts psc
        WHERE psc.is_active = TRUE
          AND psc.uf IS NOT NULL
          AND (
              p_keywords IS NULL
              OR array_length(p_keywords, 1) IS NULL
              OR EXISTS (
                  SELECT 1 FROM unnest(p_keywords) kw
                  WHERE position(lower(kw) IN lower(psc.objeto_contrato)) > 0
              )
          )
        GROUP BY psc.uf
    )
    SELECT
        us.uf_sigla,
        ROUND((us.contract_count::NUMERIC / NULLIF(v_total_contratos, 0) * 100)::NUMERIC, 1)::FLOAT AS dependency_score,
        us.contract_count,
        us.total_value
    FROM uf_stats us
    ORDER BY us.contract_count DESC;
END;
$$;

COMMENT ON FUNCTION public.get_regional_dependency_index(TEXT, TEXT[])
    IS 'SUBINTEL-012 (#1681) — Indice de dependencia regional por setor. '
       'Distribuicao de contratos ativos por UF com score de dependencia (share %). '
       'Aceita keywords opcionais para filtrar por objeto_contrato.';

GRANT EXECUTE ON FUNCTION public.get_regional_dependency_index(TEXT, TEXT[]) TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_regional_dependency_index(TEXT, TEXT[]) TO service_role;
