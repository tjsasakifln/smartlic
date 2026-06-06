-- ============================================================================
-- UP: API-SELF-004 — api_subscriptions + api_usage_records tables
-- Date: 2026-06-06
-- ============================================================================
-- Context:
--   API-SELF-004 introduces Stripe-based API tier subscriptions and metered
--   billing. api_subscriptions tracks which API tier (Starter/Pro/Scale) a
--   user has subscribed to, linked to their Stripe subscription.
--   api_usage_records counts API requests per API key per month for metered
--   billing and quota enforcement.
-- ============================================================================

-- -----------------------------------------------------------------------
-- Table: api_subscriptions
-- Tracks API tier subscriptions linked to Stripe subscriptions.
-- One user can have at most one active API subscription at a time.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.api_subscriptions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID        NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    tier                TEXT        NOT NULL CHECK (tier IN ('api_starter', 'api_pro', 'api_scale')),
    status              TEXT        NOT NULL DEFAULT 'active'
                                    CHECK (status IN ('active', 'canceled', 'past_due', 'trialing', 'incomplete')),
    stripe_subscription_id  TEXT    UNIQUE,
    stripe_customer_id      TEXT,
    current_period_start    TIMESTAMPTZ,
    current_period_end      TIMESTAMPTZ,
    canceled_at             TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for user lookups
CREATE INDEX IF NOT EXISTS idx_api_subscriptions_user_id
    ON public.api_subscriptions(user_id);

-- Index for active subscription lookups (filter by status)
CREATE INDEX IF NOT EXISTS idx_api_subscriptions_active
    ON public.api_subscriptions(user_id)
    WHERE status = 'active';

-- Index for Stripe subscription ID lookups (webhook matching)
CREATE INDEX IF NOT EXISTS idx_api_subscriptions_stripe_sub_id
    ON public.api_subscriptions(stripe_subscription_id)
    WHERE stripe_subscription_id IS NOT NULL;

-- Enable RLS
ALTER TABLE public.api_subscriptions ENABLE ROW LEVEL SECURITY;

-- Users can view their own subscriptions
CREATE POLICY "Users can view own api subscriptions"
    ON public.api_subscriptions FOR SELECT
    USING (auth.uid() = user_id);

-- service_role bypasses RLS for admin/webhook operations

-- -----------------------------------------------------------------------
-- Table: api_usage_records
-- Tracks API request counts per API key per month for metered billing.
-- Each row represents total requests for one API key in one calendar month.
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.api_usage_records (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    api_key_id      UUID        NOT NULL REFERENCES public.api_keys(id) ON DELETE CASCADE,
    user_id         UUID        NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    month           TEXT        NOT NULL CHECK (month ~ '^\d{4}-\d{2}$'),
    request_count   INT         NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One record per API key per month
    CONSTRAINT uq_api_usage_key_month UNIQUE (api_key_id, month)
);

-- Index for querying usage by user + month
CREATE INDEX IF NOT EXISTS idx_api_usage_user_month
    ON public.api_usage_records(user_id, month);

-- Index for querying usage by API key + month (aggregation path)
CREATE INDEX IF NOT EXISTS idx_api_usage_key_month
    ON public.api_usage_records(api_key_id, month);

-- Enable RLS
ALTER TABLE public.api_usage_records ENABLE ROW LEVEL SECURITY;

-- Users can view their own usage records
CREATE POLICY "Users can view own api usage"
    ON public.api_usage_records FOR SELECT
    USING (auth.uid() = user_id);

-- -----------------------------------------------------------------------
-- Table: api_metered_billing_cron_log
-- Logs for the metered billing cron runs (audit trail)
-- -----------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.api_metered_billing_cron_log (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    month           TEXT        NOT NULL,
    records_updated INT         NOT NULL DEFAULT 0,
    total_requests  INT         NOT NULL DEFAULT 0,
    errors          TEXT,
    status          TEXT        NOT NULL DEFAULT 'completed'
                                    CHECK (status IN ('completed', 'failed', 'partially_completed'))
);

-- -----------------------------------------------------------------------
-- Profiles: add api_tier column for quick lookup
-- -----------------------------------------------------------------------
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS api_tier TEXT DEFAULT NULL
    CHECK (api_tier IS NULL OR api_tier IN ('api_starter', 'api_pro', 'api_scale'));

COMMENT ON COLUMN public.profiles.api_tier IS 'API-SELF-004: Current API tier for self-service API key users. NULL means no API subscription.';
