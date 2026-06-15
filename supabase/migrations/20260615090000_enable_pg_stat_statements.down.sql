-- Rollback: Drop pg_stat_statements extension
--
-- WARNING: This drops ALL historical query statistics. Only run during
-- maintenance windows when you are okay losing the stats.

DROP EXTENSION IF EXISTS pg_stat_statements CASCADE;

-- Revoke access granted by the up migration
REVOKE SELECT ON extensions.pg_stat_statements_info FROM service_role;
REVOKE SELECT ON extensions.pg_stat_statements FROM service_role;
REVOKE USAGE ON SCHEMA extensions FROM service_role;
