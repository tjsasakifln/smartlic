-- ============================================================================
-- DOWN: predict_seasonal_calendar — reverts 20260601000002
-- Issue: #1266
-- ============================================================================

DROP FUNCTION IF EXISTS public.predict_seasonal_calendar(VARCHAR, TEXT[], INT);
