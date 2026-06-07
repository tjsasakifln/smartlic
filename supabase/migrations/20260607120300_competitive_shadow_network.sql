-- Migration: competitive_shadow_network
-- Purpose: Grafo de co-ocorrência de fornecedores — revela consórcios,
--           subcontratações prováveis e concorrentes diretos.
-- Epic: EPIC-COMPINT (#1261) — COMPINT-010 (Mapa de Território Competitivo)
-- Source: pncp_supplier_contracts
--
-- relationship_type:
--   'consorcio_provavel'    — aparecem juntos nos mesmos editais >5x
--   'subcontratacao_provavel' — um é muito maior que o outro no mesmo órgão
--   'concorrente_direto'     — competem nos mesmos órgãos, valores similares

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.competitive_shadow_network(
    p_cnpj TEXT
)
RETURNS TABLE(
    related_cnpj TEXT,
    related_name TEXT,
    co_occurrence_count INT,
    shared_orgaos JSONB,
    last_seen_together DATE,
    relationship_type TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cnpj_clean TEXT;
BEGIN
    -- Sanitize: keep only digits
    v_cnpj_clean := regexp_replace(p_cnpj, '[^0-9]', '', 'g');
    IF length(v_cnpj_clean) <> 14 THEN
        RAISE EXCEPTION 'CNPJ inválido: deve ter 14 dígitos. Fornecido: %', p_cnpj
            USING ERRCODE = '22000';  -- data_exception
    END IF;

    RETURN QUERY
    WITH target_orgaos AS (
        -- Find all órgãos where this CNPJ has contracts
        SELECT DISTINCT psc.orgao_cnpj, psc.orgao_nome, psc.uf
        FROM pncp_supplier_contracts psc
        WHERE psc.ni_fornecedor = v_cnpj_clean
          AND psc.is_active = TRUE
    ),
    co_occurring AS (
        -- Find other suppliers in the same órgãos
        SELECT
            psc.ni_fornecedor AS related_cnpj,
            psc.nome_fornecedor AS related_name,
            COUNT(*)::INT AS co_occurrence_count,
            jsonb_agg(DISTINCT jsonb_build_object(
                'orgao_cnpj', psc.orgao_cnpj,
                'orgao_nome', psc.orgao_nome,
                'uf', psc.uf
            )) AS shared_orgaos,
            MAX(psc.data_assinatura) AS last_seen_together
        FROM pncp_supplier_contracts psc
        INNER JOIN target_orgaos to_ ON psc.orgao_cnpj = to_.orgao_cnpj
        WHERE psc.ni_fornecedor <> v_cnpj_clean
          AND psc.is_active = TRUE
        GROUP BY psc.ni_fornecedor, psc.nome_fornecedor
        HAVING COUNT(*) >= 1
    ),
    target_avg_value AS (
        SELECT AVG(psc.valor_global) AS avg_valor
        FROM pncp_supplier_contracts psc
        WHERE psc.ni_fornecedor = v_cnpj_clean AND psc.is_active = TRUE
    ),
    classified AS (
        SELECT
            co.related_cnpj,
            co.related_name,
            co.co_occurrence_count,
            co.shared_orgaos,
            co.last_seen_together,
            CASE
                WHEN co.co_occurrence_count >= 5 THEN 'consorcio_provavel'
                WHEN AVG(psc2.valor_global) > (SELECT avg_valor FROM target_avg_value) * 3
                     OR AVG(psc2.valor_global) * 3 < (SELECT avg_valor FROM target_avg_value)
                    THEN 'subcontratacao_provavel'
                ELSE 'concorrente_direto'
            END AS relationship_type
        FROM co_occurring co
        LEFT JOIN pncp_supplier_contracts psc2
            ON psc2.ni_fornecedor = co.related_cnpj AND psc2.is_active = TRUE
        GROUP BY co.related_cnpj, co.related_name,
                 co.co_occurrence_count, co.shared_orgaos, co.last_seen_together
    )
    SELECT
        c.related_cnpj,
        c.related_name,
        c.co_occurrence_count,
        c.shared_orgaos,
        c.last_seen_together,
        c.relationship_type
    FROM classified c
    ORDER BY c.co_occurrence_count DESC
    LIMIT 50;
END;
$$;

COMMENT ON FUNCTION public.competitive_shadow_network(TEXT)
    IS 'Grafo de co-ocorrência de fornecedores por órgão. '
       'Revela consórcios, subcontratações e concorrentes. Epic: COMPINT (#1261).';
