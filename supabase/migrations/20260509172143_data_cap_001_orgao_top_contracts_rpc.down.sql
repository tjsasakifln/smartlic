-- ============================================================================
-- DOWN: DATA-CAP-001 orgao top contracts RPC — reverses
--       20260509172143_data_cap_001_orgao_top_contracts_rpc.sql
-- Date: 2026-05-09
-- Author: @dev / @data-engineer
-- ============================================================================
-- Context:
--   Drops the get_orgao_top_contracts_json RPC. After rollback the application
--   code in backend/routes/orgao_publico.py will start failing with PGRST202
--   ("function not found") because it expects this RPC to exist — therefore
--   rolling back this migration MUST be paired with reverting the route to
--   the previous .limit(2000) implementation.
-- ============================================================================

DROP FUNCTION IF EXISTS public.get_orgao_top_contracts_json(text, integer);
