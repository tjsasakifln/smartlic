-- Migration: competitive_benchmark
-- Purpose: Compara métricas de um fornecedor vs. percentis do setor (P25, P50, P75).
--           Contextualiza performance competitiva: acima ou abaixo da média?
-- Epic: EPIC-COMPINT (#1261) — COMPINT-013 (Benchmarks Setoriais)
-- Source: pncp_supplier_contracts

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.competitive_benchmark(
    p_cnpj TEXT,
    p_setor TEXT DEFAULT NULL
)
RETURNS TABLE(
    metric_name TEXT,
    competitor_value NUMERIC,
    sector_p25 NUMERIC,
    sector_p50 NUMERIC,
    sector_p75 NUMERIC,
    competitor_percentile INT,
    interpretation TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cnpj_clean TEXT;
BEGIN
    -- Sanitize CNPJ
    v_cnpj_clean := regexp_replace(p_cnpj, '[^0-9]', '', 'g');
    IF length(v_cnpj_clean) <> 14 THEN
        RAISE EXCEPTION 'CNPJ inválido: deve ter 14 dígitos', p_cnpj
            USING ERRCODE = '22000';
    END IF;

    RETURN QUERY
    WITH competitor_stats AS (
        SELECT
            COUNT(*)::NUMERIC AS total_contratos,
            COALESCE(AVG(psc.valor_global), 0) AS ticket_medio,
            COUNT(DISTINCT psc.orgao_cnpj)::NUMERIC AS orgaos_atendidos,
            COUNT(DISTINCT psc.uf)::NUMERIC AS ufs_atuacao,
            COALESCE(SUM(psc.valor_global), 0) AS valor_total
        FROM pncp_supplier_contracts psc
        WHERE psc.ni_fornecedor = v_cnpj_clean
          AND psc.is_active = TRUE
    ),
    sector_stats AS (
        SELECT
            COUNT(*)::NUMERIC AS total_contratos,
            COALESCE(AVG(psc.valor_global), 0) AS ticket_medio,
            COUNT(DISTINCT psc.orgao_cnpj)::NUMERIC AS orgaos_atendidos,
            COUNT(DISTINCT psc.uf)::NUMERIC AS ufs_atuacao
        FROM pncp_supplier_contracts psc
        WHERE psc.is_active = TRUE
          AND psc.valor_global > 0
    ),
    percentiles AS (
        SELECT
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY supplier_total) AS p25_total,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY supplier_total) AS p50_total,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY supplier_total) AS p75_total,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY supplier_ticket) AS p25_ticket,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY supplier_ticket) AS p50_ticket,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY supplier_ticket) AS p75_ticket,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY supplier_orgaos) AS p25_orgaos,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY supplier_orgaos) AS p50_orgaos,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY supplier_orgaos) AS p75_orgaos,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY supplier_ufs) AS p25_ufs,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY supplier_ufs) AS p50_ufs,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY supplier_ufs) AS p75_ufs
        FROM (
            SELECT
                psc.ni_fornecedor,
                COUNT(*) AS supplier_total,
                AVG(psc.valor_global) AS supplier_ticket,
                COUNT(DISTINCT psc.orgao_cnpj) AS supplier_orgaos,
                COUNT(DISTINCT psc.uf) AS supplier_ufs
            FROM pncp_supplier_contracts psc
            WHERE psc.is_active = TRUE AND psc.valor_global > 0
            GROUP BY psc.ni_fornecedor
            HAVING COUNT(*) >= 3
        ) supplier_aggs
    ),
    competitor_percentiles AS (
        SELECT
            COALESCE(ROUND((SELECT COUNT(*) FROM (
                SELECT psc2.ni_fornecedor, COUNT(*) AS cnt
                FROM pncp_supplier_contracts psc2
                WHERE psc2.is_active = TRUE AND psc2.valor_global > 0
                GROUP BY psc2.ni_fornecedor
                HAVING COUNT(*) <= (SELECT total_contratos FROM competitor_stats)
            ) below_total)::NUMERIC / NULLIF(
                (SELECT COUNT(*) FROM (
                    SELECT psc3.ni_fornecedor
                    FROM pncp_supplier_contracts psc3
                    WHERE psc3.is_active = TRUE AND psc3.valor_global > 0
                    GROUP BY psc3.ni_fornecedor
                    HAVING COUNT(*) >= 3
                ) all_suppliers), 0) * 100), 0)::INT AS pct_total,
            COALESCE(ROUND((SELECT COUNT(*) FROM (
                SELECT psc2.ni_fornecedor, AVG(psc2.valor_global) AS avg_val
                FROM pncp_supplier_contracts psc2
                WHERE psc2.is_active = TRUE AND psc2.valor_global > 0
                GROUP BY psc2.ni_fornecedor
                HAVING AVG(psc2.valor_global) <= (SELECT ticket_medio FROM competitor_stats)
            ) below_ticket)::NUMERIC / NULLIF(
                (SELECT COUNT(*) FROM (
                    SELECT psc3.ni_fornecedor
                    FROM pncp_supplier_contracts psc3
                    WHERE psc3.is_active = TRUE AND psc3.valor_global > 0
                    GROUP BY psc3.ni_fornecedor
                    HAVING COUNT(*) >= 3
                ) all_suppliers_2), 0) * 100), 0)::INT AS pct_ticket,
            COALESCE(ROUND((SELECT COUNT(*) FROM (
                SELECT psc2.ni_fornecedor, COUNT(DISTINCT psc2.orgao_cnpj) AS org_cnt
                FROM pncp_supplier_contracts psc2
                WHERE psc2.is_active = TRUE AND psc2.valor_global > 0
                GROUP BY psc2.ni_fornecedor
                HAVING COUNT(DISTINCT psc2.orgao_cnpj) <= (SELECT orgaos_atendidos FROM competitor_stats)
            ) below_orgaos)::NUMERIC / NULLIF(
                (SELECT COUNT(*) FROM (
                    SELECT psc3.ni_fornecedor
                    FROM pncp_supplier_contracts psc3
                    WHERE psc3.is_active = TRUE AND psc3.valor_global > 0
                    GROUP BY psc3.ni_fornecedor
                    HAVING COUNT(*) >= 3
                ) all_suppliers_3), 0) * 100), 0)::INT AS pct_orgaos,
            COALESCE(ROUND((SELECT COUNT(*) FROM (
                SELECT psc2.ni_fornecedor, COUNT(DISTINCT psc2.uf) AS uf_cnt
                FROM pncp_supplier_contracts psc2
                WHERE psc2.is_active = TRUE AND psc2.valor_global > 0
                GROUP BY psc2.ni_fornecedor
                HAVING COUNT(DISTINCT psc2.uf) <= (SELECT ufs_atuacao FROM competitor_stats)
            ) below_ufs)::NUMERIC / NULLIF(
                (SELECT COUNT(*) FROM (
                    SELECT psc3.ni_fornecedor
                    FROM pncp_supplier_contracts psc3
                    WHERE psc3.is_active = TRUE AND psc3.valor_global > 0
                    GROUP BY psc3.ni_fornecedor
                    HAVING COUNT(*) >= 3
                ) all_suppliers_4), 0) * 100), 0)::INT AS pct_ufs
    )
    -- Metric 1: Total de contratos
    SELECT
        'Total de Contratos'::TEXT,
        cs.total_contratos,
        p.p25_total, p.p50_total, p.p75_total,
        cp.pct_total,
        CASE
            WHEN cp.pct_total >= 75 THEN 'Acima da média do setor — grande player'
            WHEN cp.pct_total >= 40 THEN 'Na média do setor'
            ELSE 'Abaixo da média do setor — pequeno player'
        END
    FROM competitor_stats cs, percentiles p, competitor_percentiles cp
    UNION ALL
    -- Metric 2: Ticket médio
    SELECT
        'Ticket Médio (R$)'::TEXT,
        cs.ticket_medio,
        p.p25_ticket, p.p50_ticket, p.p75_ticket,
        cp.pct_ticket,
        CASE
            WHEN cp.pct_ticket >= 75 THEN 'Contratos de alto valor — acima da média'
            WHEN cp.pct_ticket >= 40 THEN 'Ticket médio dentro do esperado'
            ELSE 'Contratos de baixo valor — abaixo da média'
        END
    FROM competitor_stats cs, percentiles p, competitor_percentiles cp
    UNION ALL
    -- Metric 3: Órgãos atendidos
    SELECT
        'Órgãos Atendidos'::TEXT,
        cs.orgaos_atendidos,
        p.p25_orgaos, p.p50_orgaos, p.p75_orgaos,
        cp.pct_orgaos,
        CASE
            WHEN cp.pct_orgaos >= 75 THEN 'Carteira diversificada — muitos órgãos'
            WHEN cp.pct_orgaos >= 40 THEN 'Diversificação média'
            ELSE 'Carteira concentrada — poucos órgãos'
        END
    FROM competitor_stats cs, percentiles p, competitor_percentiles cp
    UNION ALL
    -- Metric 4: UFs de atuação
    SELECT
        'UFs de Atuação'::TEXT,
        cs.ufs_atuacao,
        p.p25_ufs, p.p50_ufs, p.p75_ufs,
        cp.pct_ufs,
        CASE
            WHEN cp.pct_ufs >= 75 THEN 'Atuação nacional — muitas UFs'
            WHEN cp.pct_ufs >= 40 THEN 'Atuação regional — média de UFs'
            ELSE 'Atuação local — poucas UFs'
        END
    FROM competitor_stats cs, percentiles p, competitor_percentiles cp;
END;
$$;

COMMENT ON FUNCTION public.competitive_benchmark(TEXT, TEXT)
    IS 'Compara métricas de fornecedor vs. percentis do setor (P25/P50/P75). '
       'Epic: COMPINT (#1261).';
