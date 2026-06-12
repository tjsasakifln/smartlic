-- ============================================================================
-- DOWN: NETINT-007 — Reverte migration network_events_agg_weekly
-- Issue: #1677
-- Epic: #1263 (EPIC-NETINT)
-- ============================================================================
-- Context:
--   Reverte a migracao UP 20260612100000_network_events_agg_weekly.sql.
--   Remove tabela, indices, RLS policies, constraints e grants.
-- ============================================================================

BEGIN;

-- Remover RLS policies
DROP POLICY IF EXISTS "network_events_agg_weekly_select_anon" ON public.network_events_agg_weekly;
DROP POLICY IF EXISTS "network_events_agg_weekly_select_authenticated" ON public.network_events_agg_weekly;
DROP POLICY IF EXISTS "network_events_agg_weekly_select_service_role" ON public.network_events_agg_weekly;

-- Remover constraints e indices
ALTER TABLE IF EXISTS public.network_events_agg_weekly
    DROP CONSTRAINT IF EXISTS network_events_agg_weekly_unique;

DROP INDEX IF EXISTS idx_network_events_weekly_unique;
DROP INDEX IF EXISTS idx_network_events_weekly_semana;
DROP INDEX IF EXISTS idx_network_events_weekly_tipo_valor;

-- Revoke grants (idempotente)
REVOKE ALL ON public.network_events_agg_weekly FROM anon;
REVOKE ALL ON public.network_events_agg_weekly FROM authenticated;
REVOKE ALL ON public.network_events_agg_weekly FROM service_role;

-- Remover tabela
DROP TABLE IF EXISTS public.network_events_agg_weekly;

COMMIT;
