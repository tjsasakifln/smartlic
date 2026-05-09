-- Disk IO Pressure Mitigation — pncp_supplier_contracts
--
-- Context (2026-05-08): Supabase Pro Disk IO budget approaching depletion.
-- pg_stat_statements top consumer (queryid 5428716347732353988):
--   SELECT orgao_cnpj WHERE is_active=true AND orgao_cnpj IS NOT NULL LIMIT/OFFSET
--   → 314M shared_blks_read across 35K calls (~9K blocks/call, 70% miss ratio).
-- Existing idx_psc_orgao_cnpj is plain btree without is_active partial filter,
-- so planner may pick idx_psc_active (partial) and seq-scan inside.
--
-- Q-3119050603016953898 (objeto_contrato ILIKE + ORDER BY data_assinatura):
-- planner skips idx_psc_objeto_trgm (GIN) when ORDER+LIMIT present
-- (memory: feedback_planner_no_pick_gin_trgm_with_limit_order). Adding a
-- partial btree on data_assinatura WHERE is_active=true gives the planner a
-- cheap index-only ordered path for the ranking step.
--
-- Both indexes use CONCURRENTLY to avoid blocking writes during creation.
-- Each statement runs in its own transaction (CONCURRENTLY requirement).

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psc_orgao_cnpj_active_partial
  ON public.pncp_supplier_contracts (orgao_cnpj)
  WHERE is_active = true AND orgao_cnpj IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psc_data_assinatura_active_partial
  ON public.pncp_supplier_contracts (data_assinatura DESC)
  WHERE is_active = true;
