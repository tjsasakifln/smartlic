-- ============================================================================
-- DOWN: Remove partial composite index for fornecedor queries
-- reverses 20260611100001_contratos_fornecedor_active_index.sql
-- Date: 2026-06-11
-- Author: @dev
-- ============================================================================

DROP INDEX IF EXISTS public.idx_psc_fornecedor_active_data;
