-- ============================================================================
-- DOWN: competitor_shadow_network — reverts 20260531173803_competitor_shadow_network.sql
-- Issue: #1274
-- ============================================================================

DROP FUNCTION IF EXISTS public.competitor_shadow_network(TEXT, INT, INT);

DROP INDEX IF EXISTS idx_psc_pncp_fornecedor;
