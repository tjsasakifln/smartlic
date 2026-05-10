-- SEO-CNPJ-ALPHA-001: Substituir length >= 11 por regex CNPJ alfanumérico
-- nas funções RPC de sitemap.
--
-- Motivo: Receita Federal IN 2.229/2024 introduz CNPJs alfanuméricos
-- (formato: 12 chars [A-Z0-9] + 2 dígitos verificadores) a partir de 01/07/2026.
-- O critério anterior `length(orgao_cnpj) >= 11` aceitava CPFs (11 dígitos) e
-- strings inválidas, causando ~2.962 páginas 404 no Google Search Console.
--
-- Regex: '^[A-Z0-9]{12}[0-9]{2}$' com flag 'i' (case insensitive)
-- Rejeita: CPF (exatamente 11 dígitos), strings < 14 chars, strings > 14 chars
-- Aceita: CNPJ numérico 14 dígitos, CNPJ alfanumérico futuro (12 alnum + 2 num)

-- get_sitemap_cnpjs_json: returns JSON array of top CNPJs (no row-count cap)
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
      AND orgao_cnpj ~* '^[A-Z0-9]{12}[0-9]{2}$'
    GROUP BY orgao_cnpj
    ORDER BY bid_count DESC
    LIMIT max_results
  ) t;
$$;

-- get_sitemap_orgaos_json: returns JSON array of top órgãos (no row-count cap)
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
      AND orgao_cnpj ~* '^[A-Z0-9]{12}[0-9]{2}$'
    GROUP BY orgao_cnpj
    ORDER BY bid_count DESC
    LIMIT max_results
  ) t;
$$;

-- get_sitemap_cnpjs: returns top CNPJs sorted by bid count, for /cnpj/{cnpj} pages
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
    AND orgao_cnpj ~* '^[A-Z0-9]{12}[0-9]{2}$'
  GROUP BY orgao_cnpj
  ORDER BY bid_count DESC
  LIMIT max_results;
$$;

-- get_sitemap_orgaos: returns top órgãos sorted by bid count, for /orgaos/{cnpj} pages
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
    AND orgao_cnpj ~* '^[A-Z0-9]{12}[0-9]{2}$'
  GROUP BY orgao_cnpj
  ORDER BY bid_count DESC
  LIMIT max_results;
$$;

GRANT EXECUTE ON FUNCTION public.get_sitemap_cnpjs_json(integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_sitemap_orgaos_json(integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_sitemap_cnpjs(integer) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.get_sitemap_orgaos(integer) TO anon, authenticated, service_role;
