-- Migration: predictive_sazonalidade
-- Purpose: Agregação mensal de editais/contratos por setor × UF para
--           identificar padrões sazonais de compras governamentais.
-- Epic: EPIC-PREDINT (#1260) — PREDINT-012 (Calendário Sazonal)
-- Source: pncp_supplier_contracts (contratos) + pncp_raw_bids (editais)
-- Window: últimos 4 anos

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.predictive_sazonalidade(
    p_setor TEXT DEFAULT NULL,
    p_uf TEXT DEFAULT NULL
)
RETURNS TABLE(
    mes INT,
    ano INT,
    total_editais INT,
    valor_total NUMERIC,
    orgaos_top5 JSONB,
    uf_sigla TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cutoff_date DATE := CURRENT_DATE - INTERVAL '4 years';
BEGIN
    -- Sanitize inputs
    p_uf := upper(trim(p_uf));

    RETURN QUERY
    WITH contratos_mensais AS (
        SELECT
            EXTRACT(MONTH FROM psc.data_assinatura)::INT AS mes,
            EXTRACT(YEAR FROM psc.data_assinatura)::INT AS ano,
            psc.uf AS uf_sigla,
            COUNT(*)::INT AS total_editais,
            COALESCE(SUM(psc.valor_global), 0) AS valor_total
        FROM pncp_supplier_contracts psc
        WHERE psc.is_active = TRUE
          AND psc.data_assinatura >= v_cutoff_date
          AND psc.valor_global > 0
          AND (p_uf IS NULL OR psc.uf = p_uf)
        GROUP BY EXTRACT(MONTH FROM psc.data_assinatura)::INT,
                 EXTRACT(YEAR FROM psc.data_assinatura)::INT,
                 psc.uf
    ),
    top_orgaos AS (
        SELECT
            EXTRACT(MONTH FROM psc2.data_assinatura)::INT AS mes,
            EXTRACT(YEAR FROM psc2.data_assinatura)::INT AS ano,
            psc2.uf AS uf_sigla,
            jsonb_agg(
                jsonb_build_object(
                    'orgao', psc2.orgao_nome,
                    'total', psc2.cnt,
                    'valor', psc2.valor_orgao
                )
                ORDER BY psc2.cnt DESC
            ) FILTER (WHERE psc2.rn <= 5) AS orgaos_top5
        FROM (
            SELECT
                psc.orgao_nome,
                psc.data_assinatura,
                psc.uf,
                COUNT(*) AS cnt,
                SUM(psc.valor_global) AS valor_orgao,
                ROW_NUMBER() OVER (
                    PARTITION BY EXTRACT(MONTH FROM psc.data_assinatura)::INT,
                                 EXTRACT(YEAR FROM psc.data_assinatura)::INT,
                                 psc.uf
                    ORDER BY COUNT(*) DESC
                ) AS rn
            FROM pncp_supplier_contracts psc
            WHERE psc.is_active = TRUE
              AND psc.data_assinatura >= v_cutoff_date
              AND psc.orgao_nome IS NOT NULL
              AND (p_uf IS NULL OR psc.uf = p_uf)
            GROUP BY psc.orgao_nome, psc.data_assinatura, psc.uf
        ) psc2
        GROUP BY EXTRACT(MONTH FROM psc2.data_assinatura)::INT,
                 EXTRACT(YEAR FROM psc2.data_assinatura)::INT,
                 psc2.uf
    )
    SELECT
        cm.mes,
        cm.ano,
        cm.total_editais,
        cm.valor_total,
        COALESCE(to_.orgaos_top5, '[]'::JSONB) AS orgaos_top5,
        cm.uf_sigla
    FROM contratos_mensais cm
    LEFT JOIN top_orgaos to_
        ON cm.mes = to_.mes
        AND cm.ano = to_.ano
        AND cm.uf_sigla = to_.uf_sigla
    ORDER BY cm.ano DESC, cm.mes DESC, cm.valor_total DESC
    LIMIT 500;
END;
$$;

COMMENT ON FUNCTION public.predictive_sazonalidade(TEXT, TEXT)
    IS 'Agregação mensal de contratos por setor/UF para calendário sazonal. '
       'Janela: 4 anos. Epic: PREDINT (#1260).';
