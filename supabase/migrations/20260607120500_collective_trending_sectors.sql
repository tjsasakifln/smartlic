-- Migration: collective_trending_sectors
-- Purpose: Top setores/UFs com maior crescimento de buscas nos últimos N dias
--           vs. baseline histórica. Sinais de "o que está aquecendo" no mercado.
-- Epic: EPIC-NETINT (#1263) — NETINT-011 (Sinais de Mercado)
-- Source: search_sessions (dados 100% anonimizados e agregados)
-- Privacy: retorna apenas contagens agregadas, zero PII

SET statement_timeout = '30s';

CREATE OR REPLACE FUNCTION public.collective_trending_sectors(
    p_dias INT DEFAULT 14
)
RETURNS TABLE(
    entity_type TEXT,
    entity_name TEXT,
    growth_pct FLOAT,
    current_count INT,
    baseline_avg FLOAT,
    trend_direction TEXT
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_current_start DATE := CURRENT_DATE - p_dias;
    v_baseline_start DATE := CURRENT_DATE - (p_dias * 4);
    v_baseline_end DATE := CURRENT_DATE - p_dias;
BEGIN
    -- Validate input
    IF p_dias < 1 OR p_dias > 90 THEN
        p_dias := 14;
    END IF;

    RETURN QUERY
    WITH current_period AS (
        -- Aggregate sector searches in current window
        SELECT
            unnest(ss.sectors) AS sector_name,
            'sector'::TEXT AS etype,
            COUNT(*)::INT AS cnt
        FROM search_sessions ss
        WHERE ss.created_at >= v_current_start
          AND ss.created_at < CURRENT_DATE
          AND ss.sectors IS NOT NULL
          AND array_length(ss.sectors, 1) > 0
        GROUP BY unnest(ss.sectors)
    ),
    baseline_period AS (
        -- Same for baseline window (3x longer for stability)
        SELECT
            unnest(ss.sectors) AS sector_name,
            'sector'::TEXT AS etype,
            COUNT(*)::FLOAT / 3.0 AS avg_per_window  -- Normalize to same window size
        FROM search_sessions ss
        WHERE ss.created_at >= v_baseline_start
          AND ss.created_at < v_baseline_end
          AND ss.sectors IS NOT NULL
          AND array_length(ss.sectors, 1) > 0
        GROUP BY unnest(ss.sectors)
    ),
    current_ufs AS (
        SELECT
            unnest(ss.ufs) AS uf_name,
            'uf'::TEXT AS etype,
            COUNT(*)::INT AS cnt
        FROM search_sessions ss
        WHERE ss.created_at >= v_current_start
          AND ss.created_at < CURRENT_DATE
          AND ss.ufs IS NOT NULL
          AND array_length(ss.ufs, 1) > 0
        GROUP BY unnest(ss.ufs)
    ),
    baseline_ufs AS (
        SELECT
            unnest(ss.ufs) AS uf_name,
            'uf'::TEXT AS etype,
            COUNT(*)::FLOAT / 3.0 AS avg_per_window
        FROM search_sessions ss
        WHERE ss.created_at >= v_baseline_start
          AND ss.created_at < v_baseline_end
          AND ss.ufs IS NOT NULL
          AND array_length(ss.ufs, 1) > 0
        GROUP BY unnest(ss.ufs)
    ),
    sectors_trending AS (
        SELECT
            cp.etype AS entity_type,
            cp.sector_name AS entity_name,
            CASE
                WHEN COALESCE(bp.avg_per_window, 0) > 0 THEN
                    ROUND(((cp.cnt - bp.avg_per_window) / bp.avg_per_window * 100)::NUMERIC, 1)
                ELSE 100.0
            END AS growth_pct,
            cp.cnt AS current_count,
            COALESCE(bp.avg_per_window, 0)::FLOAT AS baseline_avg,
            CASE
                WHEN COALESCE(bp.avg_per_window, 0) = 0 THEN 'novo'
                WHEN ((cp.cnt - bp.avg_per_window) / bp.avg_per_window) > 0.2 THEN 'subindo'
                WHEN ((cp.cnt - bp.avg_per_window) / bp.avg_per_window) < -0.2 THEN 'caindo'
                ELSE 'estavel'
            END AS trend_direction
        FROM current_period cp
        LEFT JOIN baseline_period bp
            ON cp.sector_name = bp.sector_name AND cp.etype = bp.etype
        WHERE cp.cnt >= 3  -- Minimum sample size
    ),
    ufs_trending AS (
        SELECT
            cu.etype AS entity_type,
            cu.uf_name AS entity_name,
            CASE
                WHEN COALESCE(bu.avg_per_window, 0) > 0 THEN
                    ROUND(((cu.cnt - bu.avg_per_window) / bu.avg_per_window * 100)::NUMERIC, 1)
                ELSE 100.0
            END AS growth_pct,
            cu.cnt AS current_count,
            COALESCE(bu.avg_per_window, 0)::FLOAT AS baseline_avg,
            CASE
                WHEN COALESCE(bu.avg_per_window, 0) = 0 THEN 'novo'
                WHEN ((cu.cnt - bu.avg_per_window) / bu.avg_per_window) > 0.2 THEN 'subindo'
                WHEN ((cu.cnt - bu.avg_per_window) / bu.avg_per_window) < -0.2 THEN 'caindo'
                ELSE 'estavel'
            END AS trend_direction
        FROM current_ufs cu
        LEFT JOIN baseline_ufs bu
            ON cu.uf_name = bu.uf_name AND cu.etype = bu.etype
        WHERE cu.cnt >= 3
    ),
    combined AS (
        SELECT * FROM sectors_trending
        UNION ALL
        SELECT * FROM ufs_trending
    )
    SELECT
        c.entity_type,
        c.entity_name,
        c.growth_pct,
        c.current_count,
        c.baseline_avg,
        c.trend_direction
    FROM combined c
    ORDER BY c.growth_pct DESC
    LIMIT 50;
END;
$$;

COMMENT ON FUNCTION public.collective_trending_sectors(INT)
    IS 'Top setores/UFs com maior crescimento de buscas. Dados 100% anonimizados. '
       'Epic: NETINT (#1263).';
