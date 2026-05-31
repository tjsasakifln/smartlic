-- ============================================================================
-- SUBINTEL-002 — RPC subcontract_regional_dependency
-- Date: 2026-05-31
-- Issue: #1226
-- Author: @dev / @data-engineer
-- ============================================================================
-- Context:
--   EPIC-SUBINTEL (#1224): subcontracting intelligence layer. Wave 0 foundation.
--
--   This RPC measures the REGIONAL DEPENDENCY of a supplier and detects the
--   "wins outside operational presence region" signal — the classic trigger
--   for local partner / subcontract need:
--
--     A supplier that wins contracts in UFs where they have little/no
--     operational mass (proxy: history concentrated in another UF) needs
--     local execution capability → subcontract opportunity for regional
--     operators.
--
--   Function: subcontract_regional_dependency(
--     p_ni_fornecedor  TEXT,          -- supplier CNPJ (digits only, 14 chars)
--     p_window_months  INT DEFAULT 24 -- analysis window in months
--   )
--   RETURNS json (scalar)
--
--   Output shape:
--     {
--       "ni_fornecedor":             "XXXXXXXXXXXXXX",
--       "distribuicao_uf":           [...],   -- per-UF window distribution
--       "distribuicao_municipio":    [...],   -- per-municipio window distribution
--       "uf_base_operacional":       "SP",    -- UF with highest historical share
--       "ufs_expansao":              [...],   -- UFs with low historical share
--       "indice_dependencia_regional": 0.42,  -- HHI over window UF shares
--       "flag_vence_fora_da_base":   true     -- any expansion UF outside base
--     }
--
--   Pattern: LANGUAGE SQL STABLE (scalar JSON → PostgREST bypasses max_rows)
--   Grants: anon, authenticated, service_role (public read of aggregated data)
--   Read:   ONLY pncp_supplier_contracts (is_active = true)
-- ============================================================================

CREATE OR REPLACE FUNCTION public.subcontract_regional_dependency(
    p_ni_fornecedor TEXT,
    p_window_months INTEGER DEFAULT 24
)
RETURNS json
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH
    -- Normalize supplier CNPJ (digits only, 14 chars)
    norm AS (
      SELECT regexp_replace(COALESCE(p_ni_fornecedor, ''), '[^0-9]', '', 'g') AS ni
    ),
    -- Analysis window start date (clamped to 1..240 months)
    win AS (
      SELECT (CURRENT_DATE - (
        GREATEST(1, LEAST(240, COALESCE(p_window_months, 24))) || ' months'
      )::INTERVAL)::DATE AS ws
    ),
    -- Recent contracts within the analysis window
    recent AS (
      SELECT uf, municipio, valor_global
      FROM pncp_supplier_contracts, norm, win
      WHERE ni_fornecedor = norm.ni
        AND is_active = TRUE
        AND data_assinatura >= win.ws
        AND length(norm.ni) = 14
    ),
    -- All historical contracts (for share comparison)
    history AS (
      SELECT uf, valor_global
      FROM pncp_supplier_contracts, norm
      WHERE ni_fornecedor = norm.ni
        AND is_active = TRUE
        AND length(norm.ni) = 14
    ),
    -- Distribution by UF within the window (value-based share_pct)
    dist_uf AS (
      SELECT
        COALESCE(uf, '??')                              AS uf,
        COUNT(*)::BIGINT                                 AS count,
        COALESCE(SUM(valor_global), 0)::NUMERIC          AS valor,
        ROUND(
          (COALESCE(SUM(valor_global), 0)
           / NULLIF(SUM(SUM(valor_global)) OVER (), 0)
          ) * 100,
          2
        )                                                AS share_pct
      FROM recent
      GROUP BY COALESCE(uf, '??')
    ),
    -- Distribution by municipio within the window
    dist_muni AS (
      SELECT
        COALESCE(municipio, '???')               AS municipio,
        COALESCE(uf, '??')                       AS uf,
        COUNT(*)::BIGINT                         AS count,
        COALESCE(SUM(valor_global), 0)::NUMERIC  AS valor
      FROM recent
      WHERE municipio IS NOT NULL AND municipio <> ''
      GROUP BY COALESCE(municipio, '???'), COALESCE(uf, '??')
    ),
    -- Historical UF distribution (all time, for base UF + expansion detection)
    hist_uf AS (
      SELECT
        COALESCE(uf, '??')                      AS uf,
        COALESCE(SUM(valor_global), 0)::NUMERIC AS valor
      FROM history
      GROUP BY COALESCE(uf, '??')
    ),
    -- Historical total contract value
    hist_total AS (
      SELECT NULLIF(SUM(valor), 0)::NUMERIC AS total FROM hist_uf
    ),
    -- Historical share per UF (value-based percentage)
    hist_share AS (
      SELECT
        uf,
        ROUND((valor / (SELECT total FROM hist_total)) * 100, 2) AS share_pct
      FROM hist_uf
      WHERE (SELECT total FROM hist_total) IS NOT NULL
    ),
    -- Base operational UF (highest historical share by value)
    uf_base AS (
      SELECT uf
      FROM hist_share
      ORDER BY share_pct DESC
      LIMIT 1
    ),
    -- Expansion UFs: recent contracts but low historical share, outside base
    -- Threshold: share_historico_pct < 10% indicates marginal presence
    uf_expansao AS (
      SELECT
        r.uf,
        r.count                          AS contratos_recentes,
        COALESCE(h.share_pct, 0)         AS share_historico_pct,
        TRUE                             AS flag_fora_da_base
      FROM dist_uf r
      LEFT JOIN hist_share h ON h.uf = r.uf
      WHERE r.uf <> COALESCE((SELECT uf FROM uf_base), '')
        AND COALESCE(h.share_pct, 0) < 10.0
    ),
    -- HHI (Herfindahl-Hirschman Index) over window UF shares
    -- Formula: SUM(share_pct^2) / 10000 → [0, 1], higher = more concentrated
    hhi AS (
      SELECT ROUND(
        (SUM(share_pct * share_pct) / 10000.0)::NUMERIC,
        4
      ) AS indice
      FROM dist_uf
      WHERE share_pct > 0
    )
  -- Assemble final JSON payload
  SELECT json_build_object(
    'ni_fornecedor',
      COALESCE((SELECT ni FROM norm WHERE length(ni) = 14), p_ni_fornecedor),
    'distribuicao_uf', COALESCE(
      (SELECT json_agg(
        json_build_object(
          'uf', uf, 'count', count, 'valor', valor, 'share_pct', share_pct
        ) ORDER BY share_pct DESC
      ) FROM dist_uf),
      '[]'::json
    ),
    'distribuicao_municipio', COALESCE(
      (SELECT json_agg(
        json_build_object(
          'municipio', municipio, 'uf', uf, 'count', count, 'valor', valor
        ) ORDER BY count DESC
      ) FROM dist_muni),
      '[]'::json
    ),
    'uf_base_operacional', (SELECT uf FROM uf_base),
    'ufs_expansao', COALESCE(
      (SELECT json_agg(
        json_build_object(
          'uf', uf,
          'contratos_recentes', contratos_recentes,
          'share_historico_pct', share_historico_pct,
          'flag_fora_da_base', flag_fora_da_base
        ) ORDER BY share_historico_pct DESC
      ) FROM uf_expansao),
      '[]'::json
    ),
    'indice_dependencia_regional', COALESCE((SELECT indice FROM hhi), 0),
    'flag_vence_fora_da_base', EXISTS(SELECT 1 FROM uf_expansao)
  );
$$;

COMMENT ON FUNCTION public.subcontract_regional_dependency(TEXT, INTEGER) IS
  'SUBINTEL-002 — Regional dependency analysis for supplier. HHI + expansion UFs detection. SECURITY DEFINER, public read.';

GRANT EXECUTE ON FUNCTION public.subcontract_regional_dependency(TEXT, INTEGER)
  TO anon, authenticated, service_role;
