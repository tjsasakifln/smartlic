-- ============================================================================
-- DOWN: API-SELF-004 — reverses api_subscriptions + api_usage_records tables
-- Date: 2026-06-06
-- ============================================================================

-- Profile api_tier column
ALTER TABLE public.profiles
    DROP COLUMN IF EXISTS api_tier;

-- API metered billing cron log
DROP TABLE IF EXISTS public.api_metered_billing_cron_log CASCADE;

-- API usage records
DROP INDEX IF EXISTS public.idx_api_usage_key_month;
DROP INDEX IF EXISTS public.idx_api_usage_user_month;
DROP POLICY IF EXISTS "Users can view own api usage" ON public.api_usage_records;
DROP TABLE IF EXISTS public.api_usage_records CASCADE;

-- API subscriptions
DROP INDEX IF EXISTS public.idx_api_subscriptions_user_id;
DROP INDEX IF EXISTS public.idx_api_subscriptions_active;
DROP INDEX IF EXISTS public.idx_api_subscriptions_stripe_sub_id;
DROP POLICY IF EXISTS "Users can view own api subscriptions" ON public.api_subscriptions;
DROP TABLE IF EXISTS public.api_subscriptions CASCADE;
