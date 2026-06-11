-- ============================================================================
-- DOWN: widget_competitive_intel_rpc — Remove the RPC function
-- Date: 2026-06-11
-- Issue: #1619
-- ============================================================================

DROP FUNCTION IF EXISTS public.widget_competitive_intel(TEXT, TEXT[], TEXT, INTEGER);
