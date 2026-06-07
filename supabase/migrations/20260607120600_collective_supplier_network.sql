-- Migration: collective_supplier_network
-- Purpose: Rede de fornecedores para visualização force-directed graph.
--           Mostra conexões entre fornecedores que co-ocorrem nos mesmos órgãos.
-- Epic: EPIC-NETINT (#1263) — NETINT-012 (Network Graph)
-- Source: pncp_supplier_contracts

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.collective_supplier_network(
    p_orgao_cnpj TEXT DEFAULT NULL,
    p_min_cooccurrence INT DEFAULT 2
)
RETURNS TABLE(
    source_cnpj TEXT,
    source_name TEXT,
    target_cnpj TEXT,
    target_name TEXT,
    weight INT,
    shared_orgaos JSONB
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
BEGIN
    -- Validate min_cooccurrence
    IF p_min_cooccurrence < 1 THEN
        p_min_cooccurrence := 2;
    END IF;

    RETURN QUERY
    WITH pairs AS (
        SELECT
            a.ni_fornecedor AS source_cnpj,
            a.nome_fornecedor AS source_name,
            b.ni_fornecedor AS target_cnpj,
            b.nome_fornecedor AS target_name,
            a.orgao_cnpj,
            a.orgao_nome,
            COUNT(*)::INT AS pair_count
        FROM pncp_supplier_contracts a
        INNER JOIN pncp_supplier_contracts b
            ON a.orgao_cnpj = b.orgao_cnpj
            AND a.ni_fornecedor < b.ni_fornecedor  -- Avoid duplicates and self-pairs
        WHERE a.is_active = TRUE
          AND b.is_active = TRUE
          AND (p_orgao_cnpj IS NULL OR a.orgao_cnpj = p_orgao_cnpj)
        GROUP BY a.ni_fornecedor, a.nome_fornecedor,
                 b.ni_fornecedor, b.nome_fornecedor,
                 a.orgao_cnpj, a.orgao_nome
    ),
    aggregated AS (
        SELECT
            p.source_cnpj,
            p.source_name,
            p.target_cnpj,
            p.target_name,
            SUM(p.pair_count)::INT AS weight,
            jsonb_agg(DISTINCT jsonb_build_object(
                'orgao_cnpj', p.orgao_cnpj,
                'orgao_nome', p.orgao_nome,
                'count', p.pair_count
            )) AS shared_orgaos
        FROM pairs p
        GROUP BY p.source_cnpj, p.source_name, p.target_cnpj, p.target_name
        HAVING SUM(p.pair_count) >= p_min_cooccurrence
    )
    SELECT
        a.source_cnpj,
        a.source_name,
        a.target_cnpj,
        a.target_name,
        a.weight,
        a.shared_orgaos
    FROM aggregated a
    ORDER BY a.weight DESC
    LIMIT 200;
END;
$$;

COMMENT ON FUNCTION public.collective_supplier_network(TEXT, INT)
    IS 'Rede de fornecedores para visualização force-directed graph. '
       'Nós=fornecedores, arestas=co-ocorrência em órgãos. Epic: NETINT (#1263).';
