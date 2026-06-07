-- Migration: subcontract_regional_dependency
-- Purpose: Índice de dependência regional do fornecedor — onde concentra
--           contratos vs. onde tem base operacional. Revela oportunidade
--           de expansão geográfica ou risco de dependência.
-- Epic: EPIC-SUBINTEL (#1224) — SUBINTEL-012 (Índice de Dependência Regional)
-- Source: pncp_supplier_contracts

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.subcontract_regional_dependency(
    p_cnpj TEXT,
    p_uf TEXT DEFAULT NULL
)
RETURNS TABLE(
    uf_sigla TEXT,
    dependency_index FLOAT,
    contract_count INT,
    top_orgaos JSONB,
    expansion_potential TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cnpj_clean TEXT;
    v_total_contratos INT;
BEGIN
    -- Sanitize CNPJ
    v_cnpj_clean := regexp_replace(p_cnpj, '[^0-9]', '', 'g');
    IF length(v_cnpj_clean) <> 14 THEN
        RAISE EXCEPTION 'CNPJ inválido: deve ter 14 dígitos', p_cnpj
            USING ERRCODE = '22000';
    END IF;

    -- Total contracts for normalization
    SELECT COUNT(*)::INT INTO v_total_contratos
    FROM pncp_supplier_contracts psc
    WHERE psc.ni_fornecedor = v_cnpj_clean AND psc.is_active = TRUE;

    IF v_total_contratos = 0 THEN
        RETURN;
    END IF;

    RETURN QUERY
    WITH uf_stats AS (
        SELECT
            psc.uf AS uf_sigla,
            COUNT(*)::INT AS contract_count,
            -- Dependency index: share of total contracts in this UF
            ROUND((COUNT(*)::NUMERIC / NULLIF(v_total_contratos, 0) * 100)::NUMERIC, 1) AS dependency_index,
            -- Top órgãos in this UF
            (
                SELECT jsonb_agg(org_data)
                FROM (
                    SELECT jsonb_build_object(
                        'orgao_nome', psc2.orgao_nome,
                        'orgao_cnpj', psc2.orgao_cnpj,
                        'contratos', COUNT(*),
                        'valor_total', COALESCE(SUM(psc2.valor_global), 0)
                    ) AS org_data
                    FROM pncp_supplier_contracts psc2
                    WHERE psc2.ni_fornecedor = v_cnpj_clean
                      AND psc2.is_active = TRUE
                      AND psc2.uf = psc.uf
                      AND psc2.orgao_nome IS NOT NULL
                    GROUP BY psc2.orgao_nome, psc2.orgao_cnpj
                    ORDER BY COUNT(*) DESC
                    LIMIT 5
                ) top5
            ) AS top_orgaos
        FROM pncp_supplier_contracts psc
        WHERE psc.ni_fornecedor = v_cnpj_clean
          AND psc.is_active = TRUE
          AND psc.uf IS NOT NULL
          AND (p_uf IS NULL OR psc.uf = p_uf)
        GROUP BY psc.uf
    )
    SELECT
        us.uf_sigla,
        us.dependency_index,
        us.contract_count,
        COALESCE(us.top_orgaos, '[]'::JSONB) AS top_orgaos,
        CASE
            WHEN us.dependency_index >= 50 THEN 'alta_dependencia'
            WHEN us.dependency_index >= 30 THEN 'media_dependencia'
            WHEN us.dependency_index >= 10 THEN 'diversificando'
            ELSE 'baixa_presenca'
        END AS expansion_potential
    FROM uf_stats us
    ORDER BY us.dependency_index DESC;
END;
$$;

COMMENT ON FUNCTION public.subcontract_regional_dependency(TEXT, TEXT)
    IS 'Índice de dependência regional: share de contratos por UF. '
       'Revela concentração geográfica e potencial de expansão. Epic: SUBINTEL (#1224).';
