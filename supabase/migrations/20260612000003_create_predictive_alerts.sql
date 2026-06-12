-- PREDINT-024: Create predictive_alerts table for user-configurable alert rules
SET statement_timeout = 0;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE TABLE IF NOT EXISTS public.predictive_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    sector_id TEXT NOT NULL,
    alert_type TEXT NOT NULL CHECK (alert_type IN ('volume_spike','new_opportunity','recurrence','deadline_approaching')),
    threshold_value DECIMAL NOT NULL DEFAULT 0 CHECK (threshold_value >= 0),
    uf TEXT,
    enabled BOOLEAN NOT NULL DEFAULT true,
    last_triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
COMMENT ON TABLE public.predictive_alerts IS 'PREDINT-024: User-configurable predictive alerts for forecasted bid opportunities';
CREATE INDEX IF NOT EXISTS idx_predictive_alerts_user_id ON public.predictive_alerts (user_id);
CREATE INDEX IF NOT EXISTS idx_predictive_alerts_enabled ON public.predictive_alerts (enabled) WHERE enabled = true;
ALTER TABLE public.predictive_alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY predictive_alerts_select_policy ON public.predictive_alerts FOR SELECT USING (user_id = auth.uid());
CREATE POLICY predictive_alerts_insert_policy ON public.predictive_alerts FOR INSERT WITH CHECK (user_id = auth.uid());
CREATE POLICY predictive_alerts_update_policy ON public.predictive_alerts FOR UPDATE USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());
CREATE POLICY predictive_alerts_delete_policy ON public.predictive_alerts FOR DELETE USING (user_id = auth.uid());
CREATE OR REPLACE FUNCTION public.update_predictive_alerts_updated_at() RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql SECURITY DEFINER;
DROP TRIGGER IF EXISTS trg_predictive_alerts_updated_at ON public.predictive_alerts;
CREATE TRIGGER trg_predictive_alerts_updated_at BEFORE UPDATE ON public.predictive_alerts FOR EACH ROW EXECUTE FUNCTION public.update_predictive_alerts_updated_at();
