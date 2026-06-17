-- Issue #1916: Database connection pool monitoring RPC
-- Exposes real-time pg_stat_activity connection counts via a
-- SECURITY DEFINER function callable from the backend.
--
-- Called by backend/monitoring/db_pool_monitor.py via sb.rpc("get_db_pool_stats")

CREATE OR REPLACE FUNCTION public.get_db_pool_stats()
RETURNS json
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
  SELECT json_build_object(
    'active_connections',      (SELECT count(*) FROM pg_stat_activity WHERE state = 'active'),
    'idle_connections',        (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle'),
    'idle_in_transaction',     (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction'),
    'total_connections',       (SELECT count(*) FROM pg_stat_activity),
    'max_connections',         (SELECT current_setting('max_connections')::int),
    'waiting_connections',     (SELECT count(*) FROM pg_stat_activity WHERE wait_event IS NOT NULL AND state = 'active')
  );
$$;
