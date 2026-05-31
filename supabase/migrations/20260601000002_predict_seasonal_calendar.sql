-- ============================================================================
-- PREDINT-003: RPC predict_seasonal_calendar — calendario sazonal de compras
-- Issue: #1266
-- ============================================================================
-- Context:
--   Wave 0 RPC for Predictive Intelligence EPIC (#1260). Aggregates
--   historical contract/bid data by month to build a seasonal purchase
--   calendar for a given UF and optional sector filter.
--
--   Sources (read-only):
--     - pncp_supplier_contracts  (primary: has setor_classificado)
--     - pncp_raw_bids            (secondary: UF + date + value)
--
--   Logic per month entry:
--     volume_medio:       average total monthly value across N years
--     quantidade_media:   average number of contracts/opportunities per month
--     setor_dominante:    most frequent sector in that month
--     orgaos_principais:  top 5 orgs by frequency in that month
--     indice_sazonalidade:abs(month_avg - overall_avg) / overall_avg
--                         (0 = at avg, >0 = detectable seasonality)
--     tendencia:          "crescimento" / "estabilidade" / "declinio"
--     variacao_anual:     YoY relative change (recent 2 years vs earlier)
--
--   UF without data -> empty calendario array + zeroed stats.
--
--   Performance:
--     - Index-based access on uf + data_assinatura / data_publicacao
--     - Uses only is_active + data range filters for fast index scans
--     - Scalar JSON return bypasses PostgREST max_rows=1000
--
--   SECURITY DEFINER + SET search_path = public, pg_temp per
--   SEC-SECDEF-001/002.
--   GRANT to anon, authenticated, service_role (public contract data).
-- ============================================================================

CREATE OR REPLACE FUNCTION public.predict_seasonal_calendar(
    p_uf VARCHAR(2),
    p_setores TEXT[] DEFAULT NULL,
    p_anos_historico INT DEFAULT 5
)
RETURNS json
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
WITH
-- ============================================================================
-- Step 1: Parameter setup and time window
-- ============================================================================
params AS (
    SELECT
        UPPER(p_uf)                                            AS uf,
        (CURRENT_DATE - (p_anos_historico || ' years')::INTERVAL)::date
                                                                 AS window_start,
        CURRENT_DATE::date                                       AS window_end
),

-- ============================================================================
-- Step 2: Unified data view — merge contracts and bids
-- ============================================================================
unified AS (
    SELECT
        EXTRACT(YEAR  FROM c.data_assinatura)::int AS ano,
        EXTRACT(MONTH FROM c.data_assinatura)::int AS mes,
        COALESCE(c.valor_global, 0)::numeric       AS valor,
        COALESCE(c.setor_classificado, 'sem_classificacao') AS setor,
        COALESCE(c.orgao_nome, 'NAO_INFORMADO')    AS orgao
    FROM pncp_supplier_contracts c, params p
    WHERE c.is_active = TRUE
      AND c.data_assinatura >= p.window_start
      AND c.data_assinatura <  p.window_end
      AND c.uf = p.uf
      AND (p_setores IS NULL OR c.setor_classificado = ANY(p_setores))

    UNION ALL

    SELECT
        EXTRACT(YEAR  FROM b.data_publicacao)::int AS ano,
        EXTRACT(MONTH FROM b.data_publicacao)::int AS mes,
        COALESCE(b.valor_total_estimado, 0)::numeric AS valor,
        'sem_classificacao'::text                  AS setor,
        COALESCE(b.orgao_razao_social, 'NAO_INFORMADO') AS orgao
    FROM pncp_raw_bids b, params p
    WHERE b.is_active = TRUE
      AND b.data_publicacao >= p.window_start
      AND b.data_publicacao <  p.window_end
      AND b.uf = p.uf
),

-- ============================================================================
-- Step 3: Has-data flag
-- ============================================================================
has_data AS (
    SELECT COUNT(*)::int > 0 AS flag FROM unified
),

-- ============================================================================
-- Step 4: Twelve-month series (guarantees exactly 12 entries in output)
-- ============================================================================
months_series AS (
    SELECT generate_series(1, 12) AS mes
),

-- ============================================================================
-- Step 5: Year-Month aggregates (sum of volume, count of items)
-- ============================================================================
ym_agg AS (
    SELECT
        u.ano,
        u.mes,
        COUNT(*)::numeric AS quantidade,
        SUM(u.valor)::numeric AS volume
    FROM unified u
    GROUP BY u.ano, u.mes
),

-- ============================================================================
-- Step 6: Per-month statistics (averages across all years)
-- ============================================================================
monthly_stats AS (
    SELECT
        ms.mes,
        COALESCE(ROUND(AVG(ya.volume)::numeric, 2), 0::numeric)
            AS volume_medio,
        COALESCE(ROUND(AVG(ya.quantidade)::numeric, 1), 0::numeric)
            AS quantidade_media
    FROM months_series ms
    LEFT JOIN ym_agg ya ON ya.mes = ms.mes
    GROUP BY ms.mes
),

-- ============================================================================
-- Step 7: Overall monthly average
-- ============================================================================
overall_avg AS (
    SELECT
        CASE
            WHEN COUNT(*) > 0 AND AVG(volume_medio) > 0
            THEN AVG(volume_medio)
            ELSE NULL::numeric
        END AS avg_month_volume
    FROM monthly_stats
),

-- ============================================================================
-- Step 8: Trend — compare last 2 complete years vs earlier years
--          Current (incomplete) year is excluded from trend calc.
-- ============================================================================
trend AS (
    SELECT
        ms.mes,
        ROUND(AVG(ya.volume) FILTER (
            WHERE ya.ano >= EXTRACT(YEAR FROM p.window_end) - 2
              AND ya.ano <  EXTRACT(YEAR FROM p.window_end)
        )::numeric, 2) AS recent_avg,
        ROUND(AVG(ya.volume) FILTER (
            WHERE ya.ano < EXTRACT(YEAR FROM p.window_end) - 2
        )::numeric, 2) AS hist_avg
    FROM months_series ms
    LEFT JOIN ym_agg ya ON ya.mes = ms.mes
    CROSS JOIN params p
    GROUP BY ms.mes
),

-- ============================================================================
-- Step 9: Sector dominance per month (most frequent sector, only from contracts)
-- ============================================================================
sector_dominance AS (
    SELECT DISTINCT ON (sub.mes)
        sub.mes,
        sub.setor
    FROM (
        SELECT
            u.mes,
            u.setor,
            COUNT(*) AS cnt
        FROM unified u
        WHERE u.setor IS NOT NULL
          AND u.setor != 'sem_classificacao'
        GROUP BY u.mes, u.setor
    ) sub
    ORDER BY sub.mes, sub.cnt DESC
),

-- ============================================================================
-- Step 10: Top 5 orgaos per month
-- ============================================================================
top_orgs AS (
    SELECT
        sub.mes,
        json_agg(sub.orgao ORDER BY sub.cnt DESC) AS orgaos_list
    FROM (
        SELECT
            u.mes,
            u.orgao,
            COUNT(*) AS cnt,
            ROW_NUMBER() OVER (
                PARTITION BY u.mes ORDER BY COUNT(*) DESC
            ) AS rn
        FROM unified u
        WHERE u.orgao IS NOT NULL
          AND u.orgao != 'NAO_INFORMADO'
        GROUP BY u.mes, u.orgao
    ) sub
    WHERE sub.rn <= 5
    GROUP BY sub.mes
),

-- ============================================================================
-- Step 11: Build calendar JSON (only when data exists)
-- ============================================================================
calendario_built AS (
    SELECT
        json_agg(
            json_build_object(
                'mes', ms.mes,
                'volume_medio', ms.volume_medio,
                'quantidade_media', ms.quantidade_media,
                'setor_dominante',
                    COALESCE(sd.setor, 'sem_classificacao'),
                'orgaos_principais',
                    COALESCE(to_.orgaos_list, '[]'::json),
                'indice_sazonalidade',
                    CASE
                        WHEN oa.avg_month_volume IS NOT NULL
                         AND oa.avg_month_volume > 0
                        THEN ROUND(
                            (ABS(ms.volume_medio - oa.avg_month_volume)
                             / oa.avg_month_volume)::numeric,
                            4
                        )::float8
                        ELSE 0::float8
                    END,
                'tendencia',
                    CASE
                        WHEN t.hist_avg IS NULL OR t.hist_avg <= 0
                            THEN 'estabilidade'
                        WHEN (t.recent_avg - t.hist_avg)
                             / NULLIF(t.hist_avg, 0) > 0.10
                            THEN 'crescimento'
                        WHEN (t.recent_avg - t.hist_avg)
                             / NULLIF(t.hist_avg, 0) < -0.10
                            THEN 'declinio'
                        ELSE 'estabilidade'
                    END,
                'variacao_anual',
                    CASE
                        WHEN t.hist_avg IS NULL OR t.hist_avg <= 0
                            THEN 0::float8
                        ELSE ROUND(
                            ((t.recent_avg - t.hist_avg)
                             / NULLIF(t.hist_avg, 0))::numeric,
                            4
                        )::float8
                    END
            )
            ORDER BY ms.mes
        ) AS calendario_json
    FROM monthly_stats ms
    LEFT JOIN sector_dominance sd   ON sd.mes = ms.mes
    LEFT JOIN top_orgs to_          ON to_.mes = ms.mes
    LEFT JOIN trend t               ON t.mes = ms.mes
    CROSS JOIN overall_avg oa
)

-- ============================================================================
-- Step 12: Final JSON assembly
-- ============================================================================
SELECT json_build_object(
    'calendario',
        CASE
            WHEN (SELECT flag FROM has_data)
            THEN COALESCE(
                (SELECT calendario_json FROM calendario_built),
                '[]'::json
            )
            ELSE '[]'::json
        END,
    'stats', json_build_object(
        'uf',                (SELECT uf FROM params),
        'anos_analisados',   p_anos_historico,
        'total_contratos_base',
            CASE
                WHEN (SELECT flag FROM has_data)
                THEN (SELECT COUNT(*)::int FROM unified)
                ELSE 0
            END,
        'mes_pico',
            CASE
                WHEN (SELECT flag FROM has_data)
                THEN (
                    SELECT ms.mes
                    FROM monthly_stats ms
                    ORDER BY ms.volume_medio DESC
                    LIMIT 1
                )
                ELSE NULL::int
            END,
        'mes_vale',
            CASE
                WHEN (SELECT flag FROM has_data)
                THEN (
                    SELECT ms.mes
                    FROM monthly_stats ms
                    WHERE ms.volume_medio > 0
                    ORDER BY ms.volume_medio ASC
                    LIMIT 1
                )
                ELSE NULL::int
            END
    )
);
$$;

COMMENT ON FUNCTION public.predict_seasonal_calendar(VARCHAR, TEXT[], INT) IS
    'PREDINT-003: Build seasonal purchase calendar from historical '
    'contract/bid data. Returns scalar JSON with 12-month calendario '
    'array + stats. Parameters: p_uf (required, UF), '
    'p_setores (optional array of sectors), '
    'p_anos_historico (years of history, default 5).';

GRANT EXECUTE ON FUNCTION public.predict_seasonal_calendar(VARCHAR, TEXT[], INT)
    TO anon, authenticated, service_role;
