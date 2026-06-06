-- ============================================================================
-- Rollback: 20260606010000_add_founder_metrics_functions
-- Issue: #1414 — FOUNDER-001
--
-- Drops all 6 founder metrics functions created by the up migration.
-- ============================================================================

BEGIN;

DROP FUNCTION IF EXISTS public.get_mrr;
DROP FUNCTION IF EXISTS public.get_churn_rate_30d;
DROP FUNCTION IF EXISTS public.get_trial_to_paid_30d;
DROP FUNCTION IF EXISTS public.get_trial_to_paid_90d;
DROP FUNCTION IF EXISTS public.get_d7_retention;
DROP FUNCTION IF EXISTS public.get_arpa;

NOTIFY pgrst, 'reload schema';

COMMIT;
