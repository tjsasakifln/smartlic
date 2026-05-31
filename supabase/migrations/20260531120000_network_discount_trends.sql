-- ============================================================================
-- NETINT-004: RPC network_discount_trends — tendencias de desconto por setor/UF
-- Date: 2026-05-31
-- Issue: #1286
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Wave 0 RPC for Network Intelligence EPIC (#1263). Calcula tendencias de
--   desconto por segmento setorial+geografico. Permite que usuarios calibrem
--   sua estrategia de precificacao contra o mercado.
--
--   Desconto = (valor_estimado - valor_homologado) / valor_estimado
--     - valor_estimado: pncp_raw_bids.valor_total_estimado
--     - valor_homologado: pncp_supplier_contracts.valor_global
--     - clamped to [0, 1]; valores negativos (premio) tratados como 0
--
--   Privacy: 100% dados publicos PNCP. Zero dados de usuario.
--
--   Performance:
--     - Indice idx_psc_numero_controle_pncp criado para acelerar JOIN
--     - statement_timeout = 15s
--     - Retorno esperado < 600ms p95
--
--   Assinatura:
--     network_discount_trends(p_setor TEXT, p_uf VARCHAR(2) DEFAULT NULL,
--                             p_meses INTEGER DEFAULT 12) RETURNS json
--
--   SECURITY DEFINER + SET search_path = public conforme padrao.
--   GRANT para anon, authenticated, service_role (dados publicos).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Indice para acelerar JOIN entre pncp_supplier_contracts e pncp_raw_bids
-- O JOIN usa psc.numero_controle_pncp = prb.pncp_id
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_psc_numero_controle_pncp
    ON pncp_supplier_contracts (numero_controle_pncp);

-- ----------------------------------------------------------------------------
-- RPC: network_discount_trends
-- Retorna tendencias de desconto por UF para o setor solicitado.
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.network_discount_trends(
    p_setor TEXT,
    p_uf VARCHAR(2) DEFAULT NULL,
    p_meses INTEGER DEFAULT 12
)
RETURNS json
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_cutoff_atual DATE;
    v_cutoff_anterior DATE;
    v_result json;
BEGIN
    -- ------------------------------------------------------------------
    -- Validacao de parametros
    -- ------------------------------------------------------------------
    IF p_setor IS NULL OR trim(p_setor) = '' THEN
        RAISE EXCEPTION 'p_setor is required';
    END IF;

    IF p_meses IS NULL OR p_meses < 1 THEN
        p_meses := 12;
    END IF;

    v_cutoff_atual := (CURRENT_DATE - (p_meses || ' months')::INTERVAL)::DATE;
    v_cutoff_anterior := (v_cutoff_atual - (p_meses || ' months')::INTERVAL)::DATE;

    -- statement_timeout local: defesa contra queries runaway
    SET LOCAL statement_timeout = '15s';

    -- ------------------------------------------------------------------
    -- CTEs de agregacao
    -- ------------------------------------------------------------------
    WITH
    -- Base: contratos com descontos calculados
    discount_base AS (
        SELECT
            psc.uf,
            psc.data_assinatura,
            prb.modalidade_nome,
            GREATEST(0, LEAST(1,
                (prb.valor_total_estimado - psc.valor_global)
                / NULLIF(prb.valor_total_estimado, 0)::numeric
            )) AS desconto
        FROM pncp_supplier_contracts psc
        INNER JOIN pncp_raw_bids prb
            ON psc.numero_controle_pncp = prb.pncp_id
            AND prb.is_active = TRUE
            AND prb.valor_total_estimado IS NOT NULL
            AND prb.valor_total_estimado > 0
        WHERE psc.is_active = TRUE
          AND psc.valor_global IS NOT NULL
          AND psc.valor_global > 0
          AND (p_uf IS NULL OR UPPER(psc.uf) = UPPER(p_uf))
          AND psc.data_assinatura >= v_cutoff_anterior
    ),
    -- Periodo atual: ultimos p_meses meses
    c AS (
        SELECT
            uf,
            COUNT(*)::integer                       AS vol,
            AVG(desconto)                           AS med,
            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY desconto) AS p25,
            PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY desconto) AS p50,
            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY desconto) AS p75,
            PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY desconto) AS p90
        FROM discount_base
        WHERE data_assinatura >= v_cutoff_atual
        GROUP BY uf
    ),
    -- Periodo anterior: p_meses meses antes do cutoff atual
    p AS (
        SELECT
            uf,
            COUNT(*)::integer AS vol,
            AVG(desconto)     AS med
        FROM discount_base
        WHERE data_assinatura >= v_cutoff_anterior
          AND data_assinatura < v_cutoff_atual
        GROUP BY uf
    ),
    -- Modalidade com maior desconto medio por UF no periodo atual
    m AS (
        SELECT DISTINCT ON (uf)
            uf,
            modalidade_nome
        FROM (
            SELECT
                uf,
                modalidade_nome,
                AVG(desconto) AS med
            FROM discount_base
            WHERE data_assinatura >= v_cutoff_atual
              AND modalidade_nome IS NOT NULL
            GROUP BY uf, modalidade_nome
        ) sub
        ORDER BY uf, med DESC
    ),
    -- Agregados nacionais (usados no stats)
    nac AS (
        SELECT
            AVG(desconto) FILTER (WHERE data_assinatura >= v_cutoff_atual) AS med_atual,
            AVG(desconto) FILTER (
                WHERE data_assinatura >= v_cutoff_anterior
                  AND data_assinatura < v_cutoff_atual
            ) AS med_ant
        FROM discount_base
    ),
    -- Montagem do array JSON de tendencias por UF
    trends_json AS (
        SELECT COALESCE(json_agg(
            json_build_object(
                'uf', COALESCE(c.uf, p.uf),
                'desconto_medio_atual', ROUND(COALESCE(c.med, 0)::numeric, 4),
                'desconto_medio_anterior', ROUND(COALESCE(p.med, 0)::numeric, 4),
                'variacao_percentual', CASE
                    WHEN COALESCE(p.med, 0) > 0
                    THEN ROUND((COALESCE(c.med, 0) - p.med) / p.med, 4)
                    ELSE 0
                END,
                'tendencia', CASE
                    WHEN COALESCE(p.med, 0) > 0
                         AND (COALESCE(c.med, 0) - p.med) / p.med < -0.10 THEN 'queda'
                    WHEN COALESCE(p.med, 0) > 0
                         AND (COALESCE(c.med, 0) - p.med) / p.med > 0.10 THEN 'alta'
                    ELSE 'estavel'
                END,
                'volume_contratos', COALESCE(c.vol, 0),
                'modalidade_mais_desconto', m.modalidade_nome,
                'p25_desconto', ROUND(COALESCE(c.p25, 0)::numeric, 4),
                'p50_desconto', ROUND(COALESCE(c.p50, 0)::numeric, 4),
                'p75_desconto', ROUND(COALESCE(c.p75, 0)::numeric, 4),
                'p90_desconto', ROUND(COALESCE(c.p90, 0)::numeric, 4)
            ) ORDER BY COALESCE(c.vol, 0) DESC
        ), '[]'::json) AS arr
        FROM c
        FULL OUTER JOIN p ON c.uf = p.uf
        LEFT JOIN m ON COALESCE(c.uf, p.uf) = m.uf
    )
    -- ------------------------------------------------------------------
    -- Montagem do payload final
    -- ------------------------------------------------------------------
    SELECT json_build_object(
        'setor', p_setor,
        'tendencias_desconto', t.arr,
        'stats', json_build_object(
            'desconto_medio_nacional', ROUND(COALESCE(n.med_atual, 0)::numeric, 4),
            'tendencia_nacional', CASE
                WHEN COALESCE(n.med_ant, 0) > 0 THEN
                    CASE
                        WHEN (n.med_atual - n.med_ant) / n.med_ant < -0.10 THEN 'queda'
                        WHEN (n.med_atual - n.med_ant) / n.med_ant > 0.10 THEN 'alta'
                        ELSE 'estavel'
                    END
                ELSE 'estavel'
            END,
            'uf_mais_agressiva', COALESCE(
                (SELECT uf FROM c ORDER BY p90 DESC LIMIT 1),
                'N/A'
            ),
            'uf_menos_agressiva', COALESCE(
                (SELECT uf FROM c ORDER BY p90 ASC LIMIT 1),
                'N/A'
            )
        )
    ) INTO v_result
    FROM trends_json t
    CROSS JOIN nac n;

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.network_discount_trends(TEXT, VARCHAR, INTEGER) IS
    'NETINT-004 — Tendencias de desconto por setor/UF. '
    'Desconto = (valor_estimado - valor_homologado)/valor_estimado, clamped [0,1]. '
    'Dados publicos PNCP. SECURITY DEFINER.';

-- Grants: dados publicos PNCP — todos os roles podem consultar
GRANT EXECUTE ON FUNCTION public.network_discount_trends(TEXT, VARCHAR, INTEGER) TO anon;
GRANT EXECUTE ON FUNCTION public.network_discount_trends(TEXT, VARCHAR, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION public.network_discount_trends(TEXT, VARCHAR, INTEGER) TO service_role;
