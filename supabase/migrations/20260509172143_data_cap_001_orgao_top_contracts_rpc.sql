-- ============================================================================
-- DATA-CAP-001 — RPC RETURNS json scalar for orgao top suppliers aggregation
-- Date: 2026-05-09
-- Author: @dev / @data-engineer
-- ============================================================================
-- Context:
--   PostgREST max_rows=1000 silently truncates table queries. The
--   /v1/orgaos/{cnpj} endpoint (orgao_publico.py::_fetch_contracts_data)
--   used to fetch up to 2000 raw contract rows from pncp_supplier_contracts
--   and aggregate in Python. With orgãos that have >1000 active contracts,
--   that truncation produced incorrect "top fornecedores" lists and
--   under-counted total_contratos_24m / valor_total_contratos_24m.
--
--   Pattern A (RETURNS json scalar) bypasses the row-cap entirely because
--   PostgREST only enforces max_rows on TABLE / SETOF returns, not on
--   scalar JSON. This RPC returns one JSON document with the pre-aggregated
--   top suppliers + totals, computed server-side.
--
-- Reference: supabase/migrations/20260408200000_sitemap_rpc_json.sql
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_orgao_top_contracts_json(
  p_orgao_cnpj text,
  p_limit integer DEFAULT 10
)
RETURNS json
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  WITH per_supplier AS (
    SELECT
      ni_fornecedor,
      MAX(nome_fornecedor) AS nome,
      COUNT(*)::bigint     AS contratos,
      COALESCE(SUM(valor_global), 0)::numeric AS valor
    FROM pncp_supplier_contracts
    WHERE orgao_cnpj = p_orgao_cnpj
      AND is_active  = true
      AND ni_fornecedor IS NOT NULL
      AND ni_fornecedor <> ''
    GROUP BY ni_fornecedor
  ),
  totals AS (
    SELECT
      COALESCE(SUM(contratos), 0)::bigint  AS total_contratos,
      COALESCE(SUM(valor),     0)::numeric AS valor_total
    FROM per_supplier
  ),
  top_n AS (
    SELECT
      nome,
      ni_fornecedor AS cnpj,
      contratos     AS total_contratos,
      ROUND(valor::numeric, 2)::float8 AS valor_total
    FROM per_supplier
    WHERE valor > 0
    ORDER BY valor DESC
    LIMIT GREATEST(p_limit, 0)
  )
  SELECT json_build_object(
    'top_fornecedores', COALESCE(
      (SELECT json_agg(t.* ORDER BY t.valor_total DESC) FROM top_n t),
      '[]'::json
    ),
    'total_contratos_24m',       (SELECT total_contratos FROM totals),
    'valor_total_contratos_24m', ROUND((SELECT valor_total FROM totals)::numeric, 2)::float8
  );
$$;

GRANT EXECUTE ON FUNCTION public.get_orgao_top_contracts_json(text, integer)
  TO anon, authenticated, service_role;

COMMENT ON FUNCTION public.get_orgao_top_contracts_json(text, integer) IS
  'DATA-CAP-001: aggregate top suppliers + totals for an orgão. Returns scalar JSON to bypass PostgREST max_rows=1000.';
