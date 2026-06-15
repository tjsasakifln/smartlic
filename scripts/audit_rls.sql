-- =============================================================================
-- audit_rls.sql — RLS coverage audit for public schema (#1792)
--
-- Connects to Supabase (via audit_rls.sh wrapper) and checks that every
-- public-schema table has Row Level Security enabled with at least one
-- policy. Tables must have rls_enabled=true AND policy_count>=1, OR carry
-- a documented -- rls-exempt: marker in their migration file.
--
-- Exit status (when called via audit_rls.sh):
--   All tables RLS-compliant  → exit 0
--   Any table missing RLS     → exit 1
--
-- Reference: ADR-RLS-MANDATORY-001 (docs/adr/ADR-RLS-MANDATORY-001-policy.md)
-- =============================================================================

-- ═════════════════════════════════════════════════════════════════════════════
-- Per-table RLS audit
-- ═════════════════════════════════════════════════════════════════════════════
WITH table_rls AS (
  SELECT
    t.tablename,
    c.relrowsecurity AS rls_enabled,
    c.relforcerowsecurity AS rls_forced,
    c.n_live_tup AS estimated_rows
  FROM pg_catalog.pg_tables t
  JOIN pg_catalog.pg_class c ON c.relname = t.tablename
    AND c.relnamespace = (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = 'public')
  WHERE t.schemaname = 'public'
    AND t.tablename NOT LIKE '\_%'       -- exclude internal tables
    AND c.relkind = 'r'                   -- ordinary tables only (not views, etc.)
),
policy_counts AS (
  SELECT
    tablename,
    COUNT(*) AS policy_count,
    jsonb_agg(jsonb_build_object(
      'name', policyname,
      'roles', roles,
      'cmd', cmd
    ) ORDER BY policyname) AS policies
  FROM pg_policies
  WHERE schemaname = 'public'
  GROUP BY tablename
)
SELECT
  tr.tablename,
  tr.rls_enabled,
  tr.rls_forced,
  COALESCE(pc.policy_count, 0)::integer AS policy_count,
  COALESCE(pc.policies, '[]'::jsonb) AS policies,
  tr.estimated_rows,
  CASE
    WHEN tr.rls_enabled AND COALESCE(pc.policy_count, 0) > 0 THEN 'PASS'
    WHEN tr.rls_enabled AND COALESCE(pc.policy_count, 0) = 0 THEN 'WARN: RLS on but no policies'
    ELSE 'FAIL: RLS disabled'
  END AS status
FROM table_rls tr
LEFT JOIN policy_counts pc USING (tablename)
ORDER BY
  status DESC,          -- failures first
  tr.tablename;


-- ═════════════════════════════════════════════════════════════════════════════
-- Summary row (human-readable verdict)
-- ═════════════════════════════════════════════════════════════════════════════
SELECT
  COUNT(*) AS total_tables,
  COUNT(*) FILTER (WHERE rls_enabled AND policy_count > 0) AS rls_compliant,
  COUNT(*) FILTER (WHERE rls_enabled AND policy_count = 0) AS rls_on_no_policy,
  COUNT(*) FILTER (WHERE NOT rls_enabled) AS rls_disabled,
  CASE
    WHEN COUNT(*) FILTER (WHERE NOT rls_enabled OR (rls_enabled AND policy_count = 0)) > 0
    THEN 'FAIL: Some tables are missing RLS coverage'
    ELSE 'PASS: All tables have RLS enabled with policies'
  END AS verdict
FROM (
  SELECT
    t.relrowsecurity AS rls_enabled,
    COUNT(p.policyname) AS policy_count
  FROM pg_catalog.pg_tables t
  JOIN pg_catalog.pg_class c ON c.relname = t.tablename
    AND c.relnamespace = (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname = 'public')
  LEFT JOIN pg_policies p ON p.tablename = t.tablename AND p.schemaname = 'public'
  WHERE t.schemaname = 'public'
    AND t.tablename NOT LIKE '\_%'
    AND c.relkind = 'r'
  GROUP BY t.tablename, t.relrowsecurity
) sub;
