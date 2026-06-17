-- Rollback for Issue #1916: Remove get_db_pool_stats RPC function
DROP FUNCTION IF EXISTS public.get_db_pool_stats();
