-- COMPINT-012 (#1666): Competitive Alerts watchlist
-- Issue: #1666
-- Adds competitive_alerts table for users to track competitor activity.

CREATE TABLE IF NOT EXISTS public.competitive_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    competitor_cnpj TEXT NOT NULL,
    alert_type TEXT NOT NULL CHECK (alert_type IN (
        'new_contract',
        'new_uf',
        'new_agency',
        'new_sector_entrant'
    )),
    metadata JSONB DEFAULT '{}'::jsonb,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- RLS: user sees only their own alerts
ALTER TABLE public.competitive_alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY competitive_alerts_user_select
    ON public.competitive_alerts
    FOR SELECT
    USING (user_id = auth.uid());

CREATE POLICY competitive_alerts_user_insert
    ON public.competitive_alerts
    FOR INSERT
    WITH CHECK (user_id = auth.uid());

CREATE POLICY competitive_alerts_user_delete
    ON public.competitive_alerts
    FOR DELETE
    USING (user_id = auth.uid());

-- Indexes for fast lookups
CREATE INDEX idx_competitive_alerts_user
    ON public.competitive_alerts(user_id);

CREATE INDEX idx_competitive_alerts_cnpj
    ON public.competitive_alerts(competitor_cnpj);

CREATE INDEX idx_competitive_alerts_type
    ON public.competitive_alerts(alert_type);

-- Notify PostgREST to reload schema cache
NOTIFY pgrst, 'reload schema';
