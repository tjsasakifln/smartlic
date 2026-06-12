-- ============================================================================
-- UP: predint_time_series — 4 RPCs for Time Series Predictive Intelligence
-- Date: 2026-06-12
-- Issue: #1664 (PREDINT-020)
-- Epic: #1260 (EPIC-PREDINT)
-- Source: pncp_supplier_contracts
--
-- Provides the fundamental data layer for all predictive components:
--   1. get_sector_monthly_volume   — monthly bid count + value for a sector
--   2. get_sector_seasonal_pattern — average monthly patterns (Jan-Dec)
--   3. get_uf_demand_trend        — monthly demand trend for a UF + sector
--   4. get_upcoming_renewals      — contracts expiring within a lookahead window
-- ============================================================================

BEGIN;

SET statement_timeout = '30s';

-- ============================================================================
-- RPC 1: get_sector_monthly_volume
-- Retorna contagem mensal de contratos + valor total agregado por mes.
-- Util para graficos de linha/barra mostrando volume de contratacoes no tempo.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.get_sector_monthly_volume(
    sector_id TEXT,
    months_back INT DEFAULT 36
)
RETURNS TABLE(
    month TEXT,
    bid_count BIGINT,
    total_value DECIMAL
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cutoff DATE;
BEGIN
    -- Clamp months_back to a reasonable range
    IF months_back < 1 OR months_back > 120 THEN
        months_back := 36;
    END IF;

    v_cutoff := (CURRENT_DATE - (months_back || ' months')::INTERVAL)::DATE;

    RETURN QUERY
    SELECT
        to_char(psc.data_assinatura, 'YYYY-MM') AS month,
        COUNT(*)::BIGINT AS bid_count,
        COALESCE(SUM(psc.valor_global), 0)::DECIMAL AS total_value
    FROM public.pncp_supplier_contracts psc
    WHERE psc.is_active = TRUE
      AND psc.data_assinatura >= v_cutoff
      AND psc.valor_global > 0
      AND psc.data_assinatura IS NOT NULL
    GROUP BY to_char(psc.data_assinatura, 'YYYY-MM')
    ORDER BY month;
END;
$$;

COMMENT ON FUNCTION public.get_sector_monthly_volume(TEXT, INT)
    IS 'PREDINT-020 (#1664) — Monthly contract volume (count + value). '
       'sector_id is accepted for API compatibility; actual data aggregation '
       'is across all sectors from pncp_supplier_contracts. '
       'months_back default 36, clamped 1-120.';

-- ============================================================================
-- RPC 2: get_sector_seasonal_pattern
-- Retorna a media mensal de contratos e valores nos ultimos 4 anos,
-- agregada por mes (1-12) para identificar padroes sazonais.
-- Util para calendario sazonal de compras governamentais.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.get_sector_seasonal_pattern(
    sector_id TEXT
)
RETURNS TABLE(
    month_num INT,
    avg_count DECIMAL,
    avg_value DECIMAL
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cutoff DATE := (CURRENT_DATE - INTERVAL '4 years')::DATE;
    v_year_count INT;
BEGIN
    -- Count how many years of data we have for averaging
    SELECT COUNT(DISTINCT EXTRACT(YEAR FROM psc.data_assinatura))::INT
    INTO v_year_count
    FROM public.pncp_supplier_contracts psc
    WHERE psc.is_active = TRUE
      AND psc.data_assinatura >= v_cutoff;

    -- Protect against division by zero
    IF v_year_count < 1 THEN
        v_year_count := 1;
    END IF;

    RETURN QUERY
    SELECT
        EXTRACT(MONTH FROM psc.data_assinatura)::INT AS month_num,
        (COUNT(*)::DECIMAL / v_year_count) AS avg_count,
        COALESCE(AVG(psc.valor_global), 0)::DECIMAL AS avg_value
    FROM public.pncp_supplier_contracts psc
    WHERE psc.is_active = TRUE
      AND psc.data_assinatura >= v_cutoff
      AND psc.valor_global > 0
      AND psc.data_assinatura IS NOT NULL
    GROUP BY EXTRACT(MONTH FROM psc.data_assinatura)::INT
    ORDER BY month_num;
END;
$$;

COMMENT ON FUNCTION public.get_sector_seasonal_pattern(TEXT)
    IS 'PREDINT-020 (#1664) — Seasonal pattern (avg monthly contracts + value, 4yr window). '
       'sector_id accepted for API compatibility. Source: pncp_supplier_contracts.';

-- ============================================================================
-- RPC 3: get_uf_demand_trend
-- Retorna a evolucao mensal de contratos para uma UF + setor especificos.
-- Util para graficos de tendencia regional de demanda.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.get_uf_demand_trend(
    uf TEXT,
    sector_id TEXT,
    months_back INT DEFAULT 24
)
RETURNS TABLE(
    month TEXT,
    bid_count BIGINT,
    total_value DECIMAL
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_cutoff DATE;
    v_uf_clean TEXT;
BEGIN
    -- Clamp months_back
    IF months_back < 1 OR months_back > 120 THEN
        months_back := 24;
    END IF;

    v_cutoff := (CURRENT_DATE - (months_back || ' months')::INTERVAL)::DATE;
    v_uf_clean := upper(trim(get_uf_demand_trend.uf));

    -- Validate UF format
    IF length(v_uf_clean) <> 2 THEN
        RAISE EXCEPTION 'invalid UF: must be a 2-letter state code, got %', v_uf_clean;
    END IF;

    RETURN QUERY
    SELECT
        to_char(psc.data_assinatura, 'YYYY-MM') AS month,
        COUNT(*)::BIGINT AS bid_count,
        COALESCE(SUM(psc.valor_global), 0)::DECIMAL AS total_value
    FROM public.pncp_supplier_contracts psc
    WHERE psc.is_active = TRUE
      AND psc.data_assinatura >= v_cutoff
      AND upper(psc.uf) = v_uf_clean
      AND psc.valor_global > 0
      AND psc.data_assinatura IS NOT NULL
    GROUP BY to_char(psc.data_assinatura, 'YYYY-MM')
    ORDER BY month;
END;
$$;

COMMENT ON FUNCTION public.get_uf_demand_trend(TEXT, TEXT, INT)
    IS 'PREDINT-020 (#1664) — Monthly demand trend for a specific UF. '
       'sector_id accepted for API compatibility. Source: pncp_supplier_contracts.';

-- ============================================================================
-- RPC 4: get_upcoming_renewals
-- Retorna contratos com vencimento estimado dentro de uma janela futura.
-- Como a tabela nao possui data de vigencia, estima expiry como
-- data_assinatura + 1 ano (heuristic for typical public contracts).
-- Util para alertas de renovacao de contratos.
-- ============================================================================
CREATE OR REPLACE FUNCTION public.get_upcoming_renewals(
    sector_id TEXT,
    lookahead_days INT DEFAULT 90
)
RETURNS TABLE(
    contract_id BIGINT,
    orgao TEXT,
    value DECIMAL,
    estimated_expiry DATE
)
LANGUAGE plpgsql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
DECLARE
    v_today DATE := CURRENT_DATE;
    v_horizon DATE;
BEGIN
    -- Clamp lookahead_days
    IF lookahead_days < 1 OR lookahead_days > 365 THEN
        lookahead_days := 90;
    END IF;

    v_horizon := (v_today + (lookahead_days || ' days')::INTERVAL)::DATE;

    RETURN QUERY
    SELECT
        psc.id AS contract_id,
        psc.orgao_nome AS orgao,
        psc.valor_global::DECIMAL AS value,
        (psc.data_assinatura + INTERVAL '1 year')::DATE AS estimated_expiry
    FROM public.pncp_supplier_contracts psc
    WHERE psc.is_active = TRUE
      AND psc.valor_global > 0
      AND psc.data_assinatura IS NOT NULL
      AND psc.orgao_nome IS NOT NULL
      -- Estimated expiry (data_assinatura + 1 year) falls within the lookahead window
      AND (psc.data_assinatura + INTERVAL '1 year')::DATE BETWEEN v_today AND v_horizon
    ORDER BY estimated_expiry ASC
    LIMIT 100;
END;
$$;

COMMENT ON FUNCTION public.get_upcoming_renewals(TEXT, INT)
    IS 'PREDINT-020 (#1664) — Contracts with estimated expiry within lookahead window. '
       'Expiry estimated as data_assinatura + 1 year (heuristic). '
       'sector_id accepted for API compatibility. Source: pncp_supplier_contracts.';

COMMIT;
