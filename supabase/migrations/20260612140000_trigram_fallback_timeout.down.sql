-- ============================================================
-- Rollback: 20260612140000_trigram_fallback_timeout
-- Issue:     #1750
-- Purpose:   Drop the wrapper RPC function
-- ============================================================

DROP FUNCTION IF EXISTS public.search_datalake_trigram_fallback_with_timeout(TEXT, TEXT[], INTEGER);
