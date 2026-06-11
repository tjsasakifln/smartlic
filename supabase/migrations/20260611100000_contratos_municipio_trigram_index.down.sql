-- ============================================================================
-- DOWN: Remove GIN trigram index on pncp_supplier_contracts.municipio
-- reverses 20260611100000_contratos_municipio_trigram_index.sql
-- Date: 2026-06-11
-- Author: @dev
-- ============================================================================

DROP INDEX IF EXISTS public.idx_psc_municipio_trgm;
