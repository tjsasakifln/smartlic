-- Rollback: reverte ALTER FUNCTION SET search_path do audit SEC-SECDEF-001 (#697).
-- WARNING: rollback REINTRODUZ vulnerabilidade analógica ao PR #696 wedge.
--
-- Restaura state pré-migration:
-- - 3 funções HIGH-risk de volta para proconfig=NULL (RESET search_path)
-- - 25 funções de volta para search_path=public (sem pg_temp)
--
-- Aplicar APENAS em hotfix emergencial onde audit migration causou regressão
-- inesperada em alguma função (improvável, ALTER FUNCTION SET search_path é
-- alteração de metadata sem efeito runtime sobre código).

BEGIN;

-- Restore HIGH-risk functions to NULL proconfig
ALTER FUNCTION public.extend_trial_atomic(p_user_id uuid, p_condition text, p_days integer, p_max_total integer) RESET search_path;
ALTER FUNCTION public.increment_share_view(share_hash character varying) RESET search_path;
ALTER FUNCTION public.sync_trial_expires_at_from_subscriptions() RESET search_path;

-- Restore MEDIUM/LOW-risk to search_path=public (pre-hardening state)
ALTER FUNCTION public.check_and_increment_quota(p_user_id uuid, p_month_year character varying, p_max_quota integer) SET search_path = public;
ALTER FUNCTION public.check_ingestion_orphans() SET search_path = public;
ALTER FUNCTION public.check_pncp_raw_bids_bloat() SET search_path = public;
ALTER FUNCTION public.cleanup_search_cache_per_user() SET search_path = public;
ALTER FUNCTION public.count_contracts_by_setor_uf(p_keywords text[], p_uf text) SET search_path = public;
ALTER FUNCTION public.get_analytics_summary(p_user_id uuid, p_start_date timestamp with time zone, p_end_date timestamp with time zone) SET search_path = public;
ALTER FUNCTION public.get_conversations_with_unread_count(p_user_id uuid, p_is_admin boolean, p_status text, p_limit integer, p_offset integer) SET search_path = public;
ALTER FUNCTION public.get_sitemap_cnpjs(max_results integer) SET search_path = public;
ALTER FUNCTION public.get_sitemap_cnpjs_json(max_results integer) SET search_path = public;
ALTER FUNCTION public.get_sitemap_orgaos(max_results integer) SET search_path = public;
ALTER FUNCTION public.get_sitemap_orgaos_json(max_results integer) SET search_path = public;
ALTER FUNCTION public.get_table_columns_simple(p_table_name text) SET search_path = public;
ALTER FUNCTION public.get_user_billing_period(p_user_id uuid) SET search_path = public;
ALTER FUNCTION public.get_user_features(p_user_id uuid) SET search_path = public;
ALTER FUNCTION public.increment_quota_atomic(p_user_id uuid, p_month_year character varying, p_max_quota integer) SET search_path = public;
ALTER FUNCTION public.pg_total_relation_size_safe(tbl text) SET search_path = public;
ALTER FUNCTION public.prevent_privilege_escalation() SET search_path = public;
ALTER FUNCTION public.purge_old_bids(p_retention_days integer) SET search_path = public;
ALTER FUNCTION public.search_datalake(p_ufs text[], p_date_start date, p_date_end date, p_tsquery text, p_websearch_text text, p_modalidades integer[], p_valor_min numeric, p_valor_max numeric, p_esferas text[], p_modo text, p_limit integer, p_embedding vector) SET search_path = public;
ALTER FUNCTION public.search_datalake_trigram_fallback(p_query_term text, p_ufs text[], p_limit integer) SET search_path = public;
ALTER FUNCTION public.sync_profile_plan_type() SET search_path = public;
ALTER FUNCTION public.sync_subscription_status_to_profile() SET search_path = public;
ALTER FUNCTION public.upsert_pncp_raw_bids(p_records jsonb) SET search_path = public;
ALTER FUNCTION public.upsert_pncp_supplier_contracts(p_records jsonb) SET search_path = public;
ALTER FUNCTION public.user_has_feature(p_user_id uuid, p_feature_key character varying) SET search_path = public;

COMMIT;
