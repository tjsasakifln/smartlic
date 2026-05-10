-- Rollback: Reverte SEO-CNPJ-ALPHA-001
-- Restaura critério `length >= 11` nas funções RPC de sitemap.
-- AVISO: este rollback reintroduz a aceitação de CPFs (11 dígitos) e strings
-- inválidas no sitemap — aplicar apenas em emergência.

-- get_sitemap_cnpjs_json
CREATE OR REPLACE FUNCTION public.get_sitemap_cnpjs_json(max_results integer DEFAULT 5000)
RETURNS json
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COALESCE(json_agg(t.orgao_cnpj ORDER BY t.bid_count DESC), '[]'::json)
  FROM (
    SELECT orgao_cnpj, COUNT(*) AS bid_count
    FROM pncp_raw_bids
    WHERE is_active = true
      AND orgao_cnpj IS NOT NULL
      AND orgao_cnpj <> ''
      AND length(orgao_cnpj) >= 11
    GROUP BY orgao_cnpj
    ORDER BY bid_count DESC
    LIMIT max_results
  ) t;
$$;

-- get_sitemap_orgaos_json
CREATE OR REPLACE FUNCTION public.get_sitemap_orgaos_json(max_results integer DEFAULT 2000)
RETURNS json
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT COALESCE(json_agg(t.orgao_cnpj ORDER BY t.bid_count DESC), '[]'::json)
  FROM (
    SELECT orgao_cnpj, COUNT(*) AS bid_count
    FROM pncp_raw_bids
    WHERE is_active = true
      AND orgao_cnpj IS NOT NULL
      AND orgao_cnpj <> ''
      AND length(orgao_cnpj) >= 11
    GROUP BY orgao_cnpj
    ORDER BY bid_count DESC
    LIMIT max_results
  ) t;
$$;

-- get_sitemap_cnpjs
CREATE OR REPLACE FUNCTION public.get_sitemap_cnpjs(max_results integer DEFAULT 5000)
RETURNS TABLE(orgao_cnpj text, bid_count bigint)
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT orgao_cnpj, COUNT(*) AS bid_count
  FROM pncp_raw_bids
  WHERE is_active = true
    AND orgao_cnpj IS NOT NULL
    AND orgao_cnpj <> ''
    AND length(orgao_cnpj) >= 11
  GROUP BY orgao_cnpj
  ORDER BY bid_count DESC
  LIMIT max_results;
$$;

-- get_sitemap_orgaos
CREATE OR REPLACE FUNCTION public.get_sitemap_orgaos(max_results integer DEFAULT 2000)
RETURNS TABLE(orgao_cnpj text, bid_count bigint)
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT orgao_cnpj, COUNT(*) AS bid_count
  FROM pncp_raw_bids
  WHERE is_active = true
    AND orgao_cnpj IS NOT NULL
    AND orgao_cnpj <> ''
    AND length(orgao_cnpj) >= 11
  GROUP BY orgao_cnpj
  ORDER BY bid_count DESC
  LIMIT max_results;
$$;

GRANT EXECUTE ON FUNCTION public.get_sitemap_cnpjs_json(integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_sitemap_orgaos_json(integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_sitemap_cnpjs(integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_sitemap_orgaos(integer) TO anon, authenticated, service_role;
