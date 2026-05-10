-- Rollback SEO-SITEMAP-MV-001: Remove materialized views e unschedule pg_cron jobs
--
-- AVISO: Após rollback, os endpoints /sitemap/cnpjs, /sitemap/orgaos e
-- /sitemap/fornecedores-cnpj voltam a fazer queries agregadas ao vivo
-- sobre pncp_raw_bids / pncp_supplier_contracts sem o benefício de
-- pré-agregação. Aplicar apenas em emergência.

DROP MATERIALIZED VIEW IF EXISTS mv_sitemap_cnpjs;
DROP MATERIALIZED VIEW IF EXISTS mv_sitemap_orgaos;
DROP MATERIALIZED VIEW IF EXISTS mv_sitemap_fornecedores;

SELECT cron.unschedule('refresh-sitemap-mvs');
SELECT cron.unschedule('refresh-sitemap-mvs-orgaos');
SELECT cron.unschedule('refresh-sitemap-mvs-fornecedores');
