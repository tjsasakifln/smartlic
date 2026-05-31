-- ============================================================================
-- NETINT-004 (DOWN): Remove RPC network_discount_trends e indice associado
-- ============================================================================

DROP FUNCTION IF EXISTS public.network_discount_trends(TEXT, VARCHAR, INTEGER);

DROP INDEX IF EXISTS idx_psc_numero_controle_pncp;
