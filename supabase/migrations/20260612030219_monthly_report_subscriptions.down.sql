-- ============================================================================
-- DOWN: Remove monthly_report_subscriptions table and RLS policies
-- reverses 20260612030219_monthly_report_subscriptions.sql
-- Date: 2026-06-12
-- ============================================================================

DROP POLICY IF EXISTS monthly_report_subscriptions_admin_select ON public.monthly_report_subscriptions;
DROP POLICY IF EXISTS monthly_report_subscriptions_user_update ON public.monthly_report_subscriptions;
DROP POLICY IF EXISTS monthly_report_subscriptions_user_insert ON public.monthly_report_subscriptions;
DROP POLICY IF EXISTS monthly_report_subscriptions_user_select ON public.monthly_report_subscriptions;

DROP INDEX IF EXISTS public.idx_monthly_report_subscriptions_sector;
DROP INDEX IF EXISTS public.idx_monthly_report_subscriptions_status;
DROP INDEX IF EXISTS public.idx_monthly_report_subscriptions_user;

DROP TABLE IF EXISTS public.monthly_report_subscriptions;
