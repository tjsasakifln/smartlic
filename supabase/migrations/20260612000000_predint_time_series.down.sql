-- ============================================================================
-- DOWN: predint_time_series — Remove 4 Time Series RPCs
-- Date: 2026-06-12
-- Issue: #1664 (PREDINT-020)
-- Epic: #1260 (EPIC-PREDINT)
-- ============================================================================

BEGIN;

DROP FUNCTION IF EXISTS public.get_sector_monthly_volume(TEXT, INT);
DROP FUNCTION IF EXISTS public.get_sector_seasonal_pattern(TEXT);
DROP FUNCTION IF EXISTS public.get_uf_demand_trend(TEXT, TEXT, INT);
DROP FUNCTION IF EXISTS public.get_upcoming_renewals(TEXT, INT);

COMMIT;
