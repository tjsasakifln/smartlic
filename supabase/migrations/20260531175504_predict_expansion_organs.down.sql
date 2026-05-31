-- ============================================================================
-- PREDINT-005 (DOWN): Remove RPC predict_expansion_organs
-- ============================================================================

DROP FUNCTION IF EXISTS public.predict_expansion_organs(TEXT, VARCHAR, FLOAT);
