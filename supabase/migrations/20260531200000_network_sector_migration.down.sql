-- DOWN: NETINT-002 — network_sector_migration RPC
-- Removes the RPC function and index (column kept for data preservation)

DROP INDEX IF EXISTS public.idx_psc_setor_data;

DROP FUNCTION IF EXISTS public.network_sector_migration;
