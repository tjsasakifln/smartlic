-- DEBT-IO-BUDGET: Add partial indexes to reduce Disk IO for frequent query patterns.
--
-- These indexes cover the most expensive recurring queries identified in the
-- Disk IO Budget audit:
--
-- 1. new_bids_notifier: per-user COUNTs filtered by (is_active, setor_id, uf, ingested_at)
-- 2. observatorio: historical month queries filtered by (is_active, data_publicacao)
-- 3. sector_stats: daily aggregation filtered by (is_active, setor_id)
-- 4. IBGE backfill: scan for missing codigo_municipio_ibge
--
-- All indexes use WHERE is_active = true to keep index size small (~80% of queries
-- filter on active bids only).

-- Index 1: covers new_bids_notifier per-user COUNT queries
-- Query pattern: WHERE is_active AND setor_id = X AND uf IN (...) AND ingested_at >= Y
CREATE INDEX IF NOT EXISTS idx_pncp_raw_bids_active_setor_uf_ingested
    ON public.pncp_raw_bids (setor_id, uf, ingested_at)
    WHERE is_active = true;

-- Index 2: covers observatorio historical month queries
-- Query pattern: WHERE is_active AND data_publicacao BETWEEN X AND Y
CREATE INDEX IF NOT EXISTS idx_pncp_raw_bids_active_data_publicacao
    ON public.pncp_raw_bids (data_publicacao)
    WHERE is_active = true;

-- Index 3: covers sector_stats daily aggregation
-- Query pattern: WHERE is_active AND setor_id = X GROUP BY ...
CREATE INDEX IF NOT EXISTS idx_pncp_raw_bids_active_setor
    ON public.pncp_raw_bids (setor_id)
    WHERE is_active = true;

-- Index 4: covers IBGE backfill — scan for rows missing codigo_municipio_ibge
-- Query pattern: WHERE codigo_municipio_ibge IS NULL AND is_active = true
CREATE INDEX IF NOT EXISTS idx_pncp_raw_bids_missing_ibge
    ON public.pncp_raw_bids (pncp_id)
    WHERE is_active = true AND codigo_municipio_ibge IS NULL;

-- Index 5: covers organization dashboard — aggregate by orgao_cnpj for active bids
-- Query pattern: WHERE is_active AND orgao_cnpj = X (orgao_publicos routes)
CREATE INDEX IF NOT EXISTS idx_pncp_raw_bids_active_orgao_cnpj
    ON public.pncp_raw_bids (orgao_cnpj)
    WHERE is_active = true;

COMMENT ON INDEX public.idx_pncp_raw_bids_active_setor_uf_ingested IS
    'DEBT-IO-BUDGET: covers new_bids_notifier per-user COUNT queries';
COMMENT ON INDEX public.idx_pncp_raw_bids_active_data_publicacao IS
    'DEBT-IO-BUDGET: covers observatorio historical month queries';
COMMENT ON INDEX public.idx_pncp_raw_bids_active_setor IS
    'DEBT-IO-BUDGET: covers sector_stats daily aggregation';
COMMENT ON INDEX public.idx_pncp_raw_bids_missing_ibge IS
    'DEBT-IO-BUDGET: covers IBGE backfill scan for missing codigo_municipio_ibge';
COMMENT ON INDEX public.idx_pncp_raw_bids_active_orgao_cnpj IS
    'DEBT-IO-BUDGET: covers orgao_publicos and organization dashboard queries';
