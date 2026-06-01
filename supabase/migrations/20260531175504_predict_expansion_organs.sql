-- ============================================================================
-- PREDINT-005: RPC predict_expansion_organs — orgaos em expansao por CAGR
-- Date: 2026-05-31
-- Issue: #1268
-- ============================================================================
-- Context:
--   Wave 0 RPC for Predictive Intelligence EPIC (#1260). Identifica orgaos
--   publicos com tendencia de crescimento no volume de contratos nos ultimos
--   3 anos. Usa CAGR (Compound Annual Growth Rate) para medir expansao.
--
--   CAGR formula: (volume_ano_1 / volume_ano_3) ^ (1/3) - 1
--
--   Fonte: pncp_supplier_contracts (dados publicos PNCP).
--
--   Privacy: 100% dados publicos PNCP. Zero dados de usuario.
--
--   Performance:
--     - statement_timeout = 15s
--     - Indices existentes: idx_psc_data_assinatura, idx_psc_active
--     - Retorno esperado < 300ms p95
--
--   Assinatura:
--     predict_expansion_organs(p_setor TEXT DEFAULT NULL,
--                              p_uf VARCHAR(2) DEFAULT NULL,
--                              p_min_crescimento FLOAT DEFAULT 0.15)
--     RETURNS json
--
--   SECURITY DEFINER + SET search_path = public, pg_temp conforme padrao.
--   GRANT para anon, authenticated, service_role (dados publicos).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.predict_expansion_organs(
    p_setor TEXT DEFAULT NULL,
    p_uf VARCHAR(2) DEFAULT NULL,
    p_min_crescimento FLOAT DEFAULT 0.15
)
RETURNS json
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_ano_1 INTEGER;  -- last complete calendar year
    v_ano_2 INTEGER;  -- year before last
    v_ano_3 INTEGER;  -- 3 years ago
    v_result json;
BEGIN
    -- ------------------------------------------------------------------
    -- Defesa contra queries runaway
    -- ------------------------------------------------------------------
    SET LOCAL statement_timeout = '15s';

    -- ------------------------------------------------------------------
    -- Determinar os 3 anos calendario completos mais recentes
    -- Ex: se hoje = 2026-05-31, anos = 2025, 2024, 2023
    -- ------------------------------------------------------------------
    v_ano_1 := EXTRACT(YEAR FROM CURRENT_DATE)::INTEGER - 1;
    v_ano_2 := v_ano_1 - 1;
    v_ano_3 := v_ano_1 - 2;

    -- ------------------------------------------------------------------
    -- CTEs de agregacao
    -- ------------------------------------------------------------------
    WITH
    -- Base: contratos ativos com valor nos ultimos 3 anos
    base AS (
        SELECT
            psc.orgao_nome,
            psc.uf,
            psc.valor_global,
            EXTRACT(YEAR FROM psc.data_assinatura)::INTEGER AS ano,
            COALESCE(psc.setor_classificado, 'sem_classificacao') AS categoria
        FROM pncp_supplier_contracts psc
        WHERE psc.is_active = TRUE
          AND psc.valor_global IS NOT NULL
          AND psc.valor_global > 0
          AND psc.orgao_nome IS NOT NULL
          AND psc.uf IS NOT NULL
          AND psc.data_assinatura IS NOT NULL
          AND (p_uf IS NULL OR UPPER(psc.uf) = UPPER(p_uf))
          AND (p_setor IS NULL OR psc.setor_classificado = p_setor)
          AND EXTRACT(YEAR FROM psc.data_assinatura)::INTEGER IN (v_ano_1, v_ano_2, v_ano_3)
    ),
    -- Volume anual por orgao + UF
    orgao_volumes AS (
        SELECT
            orgao_nome,
            uf,
            ano,
            SUM(valor_global) AS volume_anual
        FROM base
        GROUP BY orgao_nome, uf, ano
    ),
    -- Pivot: volumes nos 3 anos por orgao
    orgao_pivot AS (
        SELECT
            orgao_nome,
            uf,
            MAX(CASE WHEN ano = v_ano_3 THEN volume_anual END) AS vol_ano_3,
            MAX(CASE WHEN ano = v_ano_2 THEN volume_anual END) AS vol_ano_2,
            MAX(CASE WHEN ano = v_ano_1 THEN volume_anual END) AS vol_ano_1
        FROM orgao_volumes
        GROUP BY orgao_nome, uf
    ),
    -- CAGR: orgaos com dados completos nos 3 anos e tendencia positiva
    orgao_com_cagr AS (
        SELECT
            orgao_nome,
            uf,
            vol_ano_3,
            vol_ano_2,
            vol_ano_1,
            (vol_ano_1 / vol_ano_3) ^ (1.0 / 3.0) - 1 AS crescimento_anual_medio,
            ARRAY[
                ROUND((vol_ano_3)::numeric, 2)::float8,
                ROUND((vol_ano_2)::numeric, 2)::float8,
                ROUND((vol_ano_1)::numeric, 2)::float8
            ] AS tendencia_3anos
        FROM orgao_pivot
        WHERE vol_ano_1 IS NOT NULL
          AND vol_ano_2 IS NOT NULL
          AND vol_ano_3 IS NOT NULL
          AND vol_ano_3 > 0
          AND vol_ano_1 > vol_ano_3  -- tendencia positiva (exclui queda)
    ),
    -- Categoria dominante do orgao (maior volume acumulado nos 3 anos)
    orgao_categoria AS (
        SELECT DISTINCT ON (orgao_nome, uf)
            sq.orgao_nome,
            sq.uf,
            sq.categoria
        FROM (
            SELECT
                orgao_nome,
                uf,
                categoria,
                SUM(valor_global) AS total_volume
            FROM base
            GROUP BY orgao_nome, uf, categoria
        ) sq
        ORDER BY sq.orgao_nome, sq.uf, sq.total_volume DESC
    ),
    -- Volume anual por categoria dentro de cada orgao
    cat_volumes AS (
        SELECT
            orgao_nome,
            uf,
            categoria,
            ano,
            SUM(valor_global) AS volume
        FROM base
        GROUP BY orgao_nome, uf, categoria, ano
    ),
    -- CAGR por categoria dentro de cada orgao
    cat_growth AS (
        SELECT
            cv.orgao_nome,
            cv.uf,
            cv.categoria,
            (MAX(CASE WHEN cv.ano = v_ano_1 THEN cv.volume END) /
             NULLIF(MAX(CASE WHEN cv.ano = v_ano_3 THEN cv.volume END), 0)
            ) ^ (1.0 / 3.0) - 1 AS crescimento
        FROM cat_volumes cv
        GROUP BY cv.orgao_nome, cv.uf, cv.categoria
        HAVING MAX(CASE WHEN cv.ano = v_ano_1 THEN cv.volume END) IS NOT NULL
           AND MAX(CASE WHEN cv.ano = v_ano_3 THEN cv.volume END) IS NOT NULL
           AND MAX(CASE WHEN cv.ano = v_ano_3 THEN cv.volume END) > 0
           AND MAX(CASE WHEN cv.ano = v_ano_1 THEN cv.volume END) >
               MAX(CASE WHEN cv.ano = v_ano_3 THEN cv.volume END)
    ),
    -- Categorias emergentes (ate 3) por orgao: crescem acima da baseline
    emergentes AS (
        SELECT
            oc.orgao_nome,
            oc.uf,
            COALESCE(
                (SELECT json_agg(sub.categoria ORDER BY sub.excesso DESC)
                 FROM (
                     SELECT cg.categoria,
                            (cg.crescimento - oc.crescimento_anual_medio) AS excesso
                     FROM cat_growth cg
                     WHERE cg.orgao_nome = oc.orgao_nome
                       AND cg.uf = oc.uf
                       AND cg.crescimento > oc.crescimento_anual_medio
                       AND cg.categoria != 'sem_classificacao'
                     ORDER BY excesso DESC
                     LIMIT 3
                 ) sub
                ),
                '[]'::json
            ) AS cats
        FROM orgao_com_cagr oc
    ),
    -- Orgaos que passaram pelo filtro p_min_crescimento
    orgaos_expandindo AS (
        SELECT
            oc.orgao_nome,
            oc.uf,
            ocat.categoria,
            ROUND(oc.crescimento_anual_medio::numeric, 4)::float8 AS crescimento_anual_medio,
            ROUND(oc.vol_ano_1::numeric, 2)::float8 AS volume_ultimo_ano,
            oc.tendencia_3anos,
            e.cats AS categorias_emergentes,
            CASE
                WHEN oc.crescimento_anual_medio > 0.30 THEN 'expansao_forte'
                ELSE 'expansao_moderada'
            END AS sinal
        FROM orgao_com_cagr oc
        LEFT JOIN orgao_categoria ocat
            ON ocat.orgao_nome = oc.orgao_nome AND ocat.uf = oc.uf
        LEFT JOIN emergentes e
            ON e.orgao_nome = oc.orgao_nome AND e.uf = oc.uf
        WHERE oc.crescimento_anual_medio >= p_min_crescimento
    ),
    -- Stats
    total_orgaos AS (
        SELECT COUNT(DISTINCT orgao_nome || '|' || uf)::INTEGER AS total
        FROM base
    ),
    expandindo_count AS (
        SELECT COUNT(*)::INTEGER AS total FROM orgaos_expandindo
    ),
    media_nacional AS (
        SELECT COALESCE(
            ROUND(AVG(crescimento_anual_medio)::numeric, 4)::float8, 0.0
        ) AS media
        FROM orgao_com_cagr
    )
    -- ------------------------------------------------------------------
    -- Montagem do payload JSON final
    -- ------------------------------------------------------------------
    SELECT json_build_object(
        'orgaos_expandindo', COALESCE(
            (SELECT json_agg(
                json_build_object(
                    'orgao_nome', oe.orgao_nome,
                    'orgao_uf', oe.uf,
                    'categoria', oe.categoria,
                    'crescimento_anual_medio', oe.crescimento_anual_medio,
                    'volume_ultimo_ano', oe.volume_ultimo_ano,
                    'tendencia_3anos', oe.tendencia_3anos,
                    'categorias_emergentes', oe.categorias_emergentes,
                    'sinal', oe.sinal
                ) ORDER BY oe.crescimento_anual_medio DESC
            ) FROM orgaos_expandindo oe),
            '[]'::json
        ),
        'stats', json_build_object(
            'orgaos_analisados', COALESCE((SELECT total FROM total_orgaos), 0),
            'expandindo', COALESCE((SELECT total FROM expandindo_count), 0),
            'crescimento_medio_nacional', COALESCE((SELECT media FROM media_nacional), 0.0)
        )
    ) INTO v_result;

    RETURN v_result;
END;
$$;

COMMENT ON FUNCTION public.predict_expansion_organs(TEXT, VARCHAR, FLOAT) IS
    'PREDINT-005 — Orgaos em expansao por CAGR. '
    'CAGR = (vol_ano_1 / vol_ano_3) ^ (1/3) - 1 sobre 3 anos completos. '
    'Dados publicos PNCP. SECURITY DEFINER.';

-- Grants: dados publicos PNCP — todos os roles podem consultar
GRANT EXECUTE ON FUNCTION public.predict_expansion_organs(TEXT, VARCHAR, FLOAT) TO anon;
GRANT EXECUTE ON FUNCTION public.predict_expansion_organs(TEXT, VARCHAR, FLOAT) TO authenticated;
GRANT EXECUTE ON FUNCTION public.predict_expansion_organs(TEXT, VARCHAR, FLOAT) TO service_role;
