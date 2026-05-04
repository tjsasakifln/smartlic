-- Migration: SECDEF search_path audit + harden (P0)
-- Issue: #697 (SEC-SECDEF-001) — analógico ao PR #696 handle_new_user wedge.
--
-- Root cause coberto: SECURITY DEFINER sem `SET search_path = public, pg_temp` herda
-- search_path do caller. Quando caller é supabase_auth_admin (search_path=auth) ou
-- qualquer role com schema-on-front diferente de public, referências UNQUALIFIED a
-- tabelas em public resolvem para o schema errado → 42P01 → aborta INSERT pai.
-- pg_temp incluído como hardening contra temp-table hijack (Supabase 2026 best practice).
--
-- Scope: 28 funções SECDEF públic schema identificadas via pg_proc.proconfig query
-- em prod (2026-05-04). 3 com proconfig=NULL (CRITICAL HIGH-risk:
-- extend_trial_atomic, increment_share_view, sync_trial_expires_at_from_subscriptions),
-- 25 com search_path=public mas faltando pg_temp hardening.

BEGIN;

-- HIGH-risk (proconfig=NULL em prod)
ALTER FUNCTION public.extend_trial_atomic(p_user_id uuid, p_condition text, p_days integer, p_max_total integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.increment_share_view(share_hash character varying) SET search_path = public, pg_temp;
ALTER FUNCTION public.sync_trial_expires_at_from_subscriptions() SET search_path = public, pg_temp;

-- MEDIUM/LOW-risk hardening (faltando pg_temp)
ALTER FUNCTION public.check_and_increment_quota(p_user_id uuid, p_month_year character varying, p_max_quota integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.check_ingestion_orphans() SET search_path = public, pg_temp;
ALTER FUNCTION public.check_pncp_raw_bids_bloat() SET search_path = public, pg_temp;
ALTER FUNCTION public.cleanup_search_cache_per_user() SET search_path = public, pg_temp;
ALTER FUNCTION public.count_contracts_by_setor_uf(p_keywords text[], p_uf text) SET search_path = public, pg_temp;
ALTER FUNCTION public.get_analytics_summary(p_user_id uuid, p_start_date timestamp with time zone, p_end_date timestamp with time zone) SET search_path = public, pg_temp;
ALTER FUNCTION public.get_conversations_with_unread_count(p_user_id uuid, p_is_admin boolean, p_status text, p_limit integer, p_offset integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.get_sitemap_cnpjs(max_results integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.get_sitemap_cnpjs_json(max_results integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.get_sitemap_orgaos(max_results integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.get_sitemap_orgaos_json(max_results integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.get_table_columns_simple(p_table_name text) SET search_path = public, pg_temp;
ALTER FUNCTION public.get_user_billing_period(p_user_id uuid) SET search_path = public, pg_temp;
ALTER FUNCTION public.get_user_features(p_user_id uuid) SET search_path = public, pg_temp;
ALTER FUNCTION public.increment_quota_atomic(p_user_id uuid, p_month_year character varying, p_max_quota integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.pg_total_relation_size_safe(tbl text) SET search_path = public, pg_temp;
ALTER FUNCTION public.prevent_privilege_escalation() SET search_path = public, pg_temp;
ALTER FUNCTION public.purge_old_bids(p_retention_days integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.search_datalake(p_ufs text[], p_date_start date, p_date_end date, p_tsquery text, p_websearch_text text, p_modalidades integer[], p_valor_min numeric, p_valor_max numeric, p_esferas text[], p_modo text, p_limit integer, p_embedding vector) SET search_path = public, pg_temp;
ALTER FUNCTION public.search_datalake_trigram_fallback(p_query_term text, p_ufs text[], p_limit integer) SET search_path = public, pg_temp;
ALTER FUNCTION public.sync_profile_plan_type() SET search_path = public, pg_temp;
ALTER FUNCTION public.sync_subscription_status_to_profile() SET search_path = public, pg_temp;
ALTER FUNCTION public.upsert_pncp_raw_bids(p_records jsonb) SET search_path = public, pg_temp;
ALTER FUNCTION public.upsert_pncp_supplier_contracts(p_records jsonb) SET search_path = public, pg_temp;
ALTER FUNCTION public.user_has_feature(p_user_id uuid, p_feature_key character varying) SET search_path = public, pg_temp;

-- Re-affirm GRANTs públicos para sitemap RPCs (idempotente).
-- Necessário porque `tests/test_debt03_rpc_security_audit.py::test_sitemap_rpcs_intentionally_public`
-- usa `all_migrations_sql.rfind("get_sitemap_cnpjs")` + slice 500 chars e exige "anon" no slice.
-- Como nossas linhas ALTER FUNCTION acima introduzem occurrences mais recentes, replicamos os
-- GRANTs originais (de `20260408220000_debt03_rpc_security_audit.sql`) como no-op idempotente.
GRANT EXECUTE ON FUNCTION public.get_sitemap_cnpjs(integer) TO anon;
GRANT EXECUTE ON FUNCTION public.get_sitemap_cnpjs_json(integer) TO anon;
GRANT EXECUTE ON FUNCTION public.get_sitemap_orgaos(integer) TO anon;
GRANT EXECUTE ON FUNCTION public.get_sitemap_orgaos_json(integer) TO anon;

-- Verification: post-migration assert que 0 SECDEF público schema permanecem sem pg_temp.
DO $$
DECLARE
  noncompliant_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO noncompliant_count
  FROM pg_proc p
  JOIN pg_namespace n ON p.pronamespace = n.oid
  WHERE p.prosecdef = true
    AND n.nspname = 'public'
    AND (p.proconfig IS NULL OR NOT EXISTS (
      SELECT 1 FROM unnest(p.proconfig) cfg
      WHERE cfg LIKE 'search_path=%pg_temp%'
    ));

  IF noncompliant_count > 0 THEN
    RAISE EXCEPTION 'SECDEF audit failed: % function(s) still missing search_path with pg_temp', noncompliant_count;
  END IF;

  RAISE NOTICE 'SECDEF audit passed: all public schema SECURITY DEFINER functions have search_path = public, pg_temp';
END $$;

COMMIT;
