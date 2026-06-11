-- ISSUE-1650: GIN trigram index on pncp_supplier_contracts.municipio
--
-- Contexto: blog_stats *_contratos endpoints filtram por cidade via
-- ILIKE '%cidade%' na coluna municipio. Sem indice trigram, cada consulta
-- faz sequential scan na tabela (2.1M+ rows), causando budget exceeded
-- (5002-5256ms observado em /v1/blog/stats/contratos/cidade/pelotas).
--
-- pg_trgm ja esta habilitado (idx_psc_objeto_trgm criado em
-- 20260413120000_contracts_trigram_index.sql).
-- Segue o mesmo padrao: SET statement_timeout=0, sem CONCURRENTLY
-- (incompativel com transacoes do Supabase CLI).

SET statement_timeout = 0;

CREATE INDEX IF NOT EXISTS idx_psc_municipio_trgm
    ON public.pncp_supplier_contracts
    USING GIN (municipio gin_trgm_ops)
    WHERE is_active = TRUE;

COMMENT ON INDEX public.idx_psc_municipio_trgm IS
    'ISSUE-1650: GIN trigram index para acelerar ILIKE %%cidade%% em blog_stats contratos queries. Reduz latencia de ~5s para <500ms em consultas por municipio.';
