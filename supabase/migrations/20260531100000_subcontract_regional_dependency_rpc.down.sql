-- ============================================================================
-- Rollback: SUBINTEL-002 — RPC subcontract_regional_dependency
-- Date: 2026-05-31
-- Issue: #1226
-- ============================================================================
-- Reverses the creation of subcontract_regional_dependency function.
-- Completely idempotent — DROP IF EXISTS is safe to run multiple times.
-- ============================================================================

DROP FUNCTION IF EXISTS public.subcontract_regional_dependency(TEXT, INTEGER);
