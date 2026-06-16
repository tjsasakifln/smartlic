-- #1866: Enable pg_stat_statements for slow query monitoring
--
-- pg_stat_statements tracks query execution statistics (planning time,
-- execution time, rows, I/O) across all databases. Supabase Cloud
-- requires shared_preload_libraries modification via support ticket,
-- but we create the extension here so the schema is ready when the
-- shared_preload_libraries change is applied.
--
-- AC1: pg_stat_statements ativado
--
-- NOTE: On Supabase, shared_preload_libraries requires a support ticket.
-- Run this migration after the preload change is confirmed.
-- Verify with: SELECT * FROM pg_stat_statements LIMIT 1;

-- Create the extension (creates the pg_stat_statements view and helper functions)
CREATE EXTENSION IF NOT EXISTS pg_stat_statements WITH SCHEMA extensions;

-- Grant access to the service_role for automated scripts
GRANT USAGE ON SCHEMA extensions TO service_role;
GRANT SELECT ON extensions.pg_stat_statements TO service_role;
GRANT SELECT ON extensions.pg_stat_statements_info TO service_role;
