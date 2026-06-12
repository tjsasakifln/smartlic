-- REPORT-MONTHLY-001 (#1620): Monthly Report Subscriptions
--
-- Tracks user subscriptions to the "Panorama Mensal de [Setor]" recurring
-- report product (R$97/mes, delivered 1st business day of each month).

SET statement_timeout = 0;

CREATE TABLE IF NOT EXISTS public.monthly_report_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
    sector_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'canceled', 'past_due')),
    stripe_sub_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(user_id, sector_id)
);

COMMENT ON TABLE public.monthly_report_subscriptions IS
    'REPORT-MONTHLY-001: User subscriptions to monthly sector reports (R$97/mes)';
COMMENT ON COLUMN public.monthly_report_subscriptions.sector_id IS 'Sector ID from sectors_data.yaml';
COMMENT ON COLUMN public.monthly_report_subscriptions.status IS 'active | canceled | past_due';
COMMENT ON COLUMN public.monthly_report_subscriptions.stripe_sub_id IS 'Stripe subscription ID for billing';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_monthly_report_subscriptions_user
    ON public.monthly_report_subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_monthly_report_subscriptions_status
    ON public.monthly_report_subscriptions (status);
CREATE INDEX IF NOT EXISTS idx_monthly_report_subscriptions_sector
    ON public.monthly_report_subscriptions (sector_id);

-- RLS
ALTER TABLE public.monthly_report_subscriptions ENABLE ROW LEVEL SECURITY;

-- Users can read their own subscriptions
CREATE POLICY monthly_report_subscriptions_user_select ON public.monthly_report_subscriptions
    FOR SELECT
    USING (user_id = auth.uid());

-- Users can insert their own subscriptions
CREATE POLICY monthly_report_subscriptions_user_insert ON public.monthly_report_subscriptions
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

-- Users can update their own subscriptions (e.g., cancel)
CREATE POLICY monthly_report_subscriptions_user_update ON public.monthly_report_subscriptions
    FOR UPDATE
    USING (user_id = auth.uid());

-- Admin can read all
CREATE POLICY monthly_report_subscriptions_admin_select ON public.monthly_report_subscriptions
    FOR SELECT
    USING (auth.uid() IN (SELECT id FROM public.profiles WHERE is_admin = true));
