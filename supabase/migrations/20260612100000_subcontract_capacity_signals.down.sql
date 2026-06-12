-- ============================================================================
-- DOWN: subcontract_capacity_signals — Remove the RPC function
-- Date: 2026-06-12
-- Issue: #1668 (SUBINTEL-001)
-- ============================================================================

DROP FUNCTION IF EXISTS public.subcontract_capacity_signals(VARCHAR, INT);
