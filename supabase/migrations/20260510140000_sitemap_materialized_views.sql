-- SEO-SITEMAP-MV-001: Materialized Views para sitemap programático
--
-- Motivação: Os endpoints /v1/sitemap/cnpjs, /v1/sitemap/orgaos e
-- /v1/sitemap/fornecedores-cnpj realizavam queries agregadas (GROUP BY +
-- COUNT) diretamente sobre pncp_raw_bids (1.5M+ rows) e
-- pncp_supplier_contracts (2M+ rows), levando de 30s a 45s por requisição.
-- Sob carga SSG (4146 páginas em paralelo), o backend saturava → timeout
-- → sitemap vazio em produção → Google abandona indexação.
--
-- Solução: Materialized Views pré-agregadas que reduzem a query para um
-- simples SELECT sem GROUP BY (< 50ms). Atualizadas diariamente via pg_cron
-- às 4h BRT (7h UTC), que é o mesmo horário do purge + ingestion complete.

-- CNPJ indexáveis: órgãos compradores com ≥1 licitação nos últimos 24 meses
CREATE MATERIALIZED VIEW mv_sitemap_cnpjs AS
SELECT DISTINCT
    orgao_cnpj AS cnpj,
    MAX(data_publicacao) AS last_seen
FROM pncp_raw_bids
WHERE orgao_cnpj ~ '^[A-Z0-9]{12}[0-9]{2}$'
  AND data_publicacao > NOW() - INTERVAL '24 months'
GROUP BY orgao_cnpj
HAVING COUNT(*) > 0;
CREATE UNIQUE INDEX ON mv_sitemap_cnpjs(cnpj);

-- Órgãos indexáveis: ≥5 licitações ativas nos últimos 12 meses
CREATE MATERIALIZED VIEW mv_sitemap_orgaos AS
SELECT DISTINCT
    orgao_cnpj AS cnpj,
    COUNT(*) AS total_licitacoes
FROM pncp_raw_bids
WHERE orgao_cnpj ~ '^[A-Z0-9]{12}[0-9]{2}$'
  AND data_publicacao > NOW() - INTERVAL '12 months'
GROUP BY orgao_cnpj
HAVING COUNT(*) >= 5;
CREATE UNIQUE INDEX ON mv_sitemap_orgaos(cnpj);

-- Fornecedores CNPJ indexáveis: ≥1 contrato nos últimos 24 meses
CREATE MATERIALIZED VIEW mv_sitemap_fornecedores AS
SELECT
    ni_fornecedor AS cnpj,
    MAX(data_assinatura) AS last_seen
FROM pncp_supplier_contracts
WHERE ni_fornecedor ~ '^[A-Z0-9]{12}[0-9]{2}$'
  AND data_assinatura > NOW() - INTERVAL '24 months'
GROUP BY ni_fornecedor
HAVING COUNT(*) > 0;
CREATE UNIQUE INDEX ON mv_sitemap_fornecedores(cnpj);

-- Refresh diário 4h BRT (7h UTC) — CONCURRENTLY para não travar leituras
SELECT cron.schedule(
    'refresh-sitemap-mvs',
    '0 7 * * *',
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sitemap_cnpjs;$$
);
SELECT cron.schedule(
    'refresh-sitemap-mvs-orgaos',
    '0 7 * * *',
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sitemap_orgaos;$$
);
SELECT cron.schedule(
    'refresh-sitemap-mvs-fornecedores',
    '0 7 * * *',
    $$REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sitemap_fornecedores;$$
);

-- Grant acesso público de leitura (POSTgREST expõe MVs como tabelas)
GRANT SELECT ON mv_sitemap_cnpjs TO anon, authenticated, service_role;
GRANT SELECT ON mv_sitemap_orgaos TO anon, authenticated, service_role;
GRANT SELECT ON mv_sitemap_fornecedores TO anon, authenticated, service_role;

COMMENT ON MATERIALIZED VIEW mv_sitemap_cnpjs IS 'Órgãos compradores indexáveis no sitemap /cnpj/{cnpj} — atualizado 4h BRT via pg_cron';
COMMENT ON MATERIALIZED VIEW mv_sitemap_orgaos IS 'Órgãos compradores indexáveis no sitemap /orgaos/{cnpj} — ≥5 licitações em 12 meses, atualizado 4h BRT via pg_cron';
COMMENT ON MATERIALIZED VIEW mv_sitemap_fornecedores IS 'Fornecedores indexáveis no sitemap /fornecedores/{cnpj} — ≥1 contrato em 24 meses, atualizado 4h BRT via pg_cron';
