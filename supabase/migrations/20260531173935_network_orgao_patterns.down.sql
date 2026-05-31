-- ============================================================================
-- NETINT-003 (DOWN): Remove RPC network_orgao_patterns
-- ============================================================================

DROP FUNCTION IF EXISTS public.network_orgao_patterns(VARCHAR, INT, INT);
