-- Rollback: drop partial indexes added for Disk IO Budget optimization.

DROP INDEX IF EXISTS public.idx_pncp_raw_bids_active_setor_uf_ingested;
DROP INDEX IF EXISTS public.idx_pncp_raw_bids_active_data_publicacao;
DROP INDEX IF EXISTS public.idx_pncp_raw_bids_active_setor;
DROP INDEX IF EXISTS public.idx_pncp_raw_bids_missing_ibge;
DROP INDEX IF EXISTS public.idx_pncp_raw_bids_active_orgao_cnpj;
