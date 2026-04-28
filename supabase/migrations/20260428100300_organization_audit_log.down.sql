-- RBAC-ORG-001 (AC8/AC9) ROLLBACK: drop organization_audit_log
--
-- Rolling this back destroys all audit history. Acceptable only in
-- recovery scenarios. The table has no incoming FKs from elsewhere in
-- the schema, so no cascade considerations.
--
-- Supabase CLI runs each migration file in its own transaction; no explicit
-- BEGIN/COMMIT needed.

DROP POLICY IF EXISTS "Org owner can read audit log"            ON public.organization_audit_log;
DROP POLICY IF EXISTS "Service role full access on org audit log" ON public.organization_audit_log;

DROP INDEX IF EXISTS public.idx_org_audit_log_org_created;
DROP INDEX IF EXISTS public.idx_org_audit_log_actor;

DROP TABLE IF EXISTS public.organization_audit_log;
