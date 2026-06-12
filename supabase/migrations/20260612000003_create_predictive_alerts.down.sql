-- DOWN: PREDINT-024 — reverses create_predictive_alerts migration
DROP TRIGGER IF EXISTS trg_predictive_alerts_updated_at ON public.predictive_alerts;
DROP FUNCTION IF EXISTS public.update_predictive_alerts_updated_at();
DROP POLICY IF EXISTS predictive_alerts_select_policy ON public.predictive_alerts;
DROP POLICY IF EXISTS predictive_alerts_insert_policy ON public.predictive_alerts;
DROP POLICY IF EXISTS predictive_alerts_update_policy ON public.predictive_alerts;
DROP POLICY IF EXISTS predictive_alerts_delete_policy ON public.predictive_alerts;
DROP INDEX IF EXISTS idx_predictive_alerts_user_id;
DROP INDEX IF EXISTS idx_predictive_alerts_enabled;
ALTER TABLE public.predictive_alerts DISABLE ROW LEVEL SECURITY;
DROP TABLE IF EXISTS public.predictive_alerts;
