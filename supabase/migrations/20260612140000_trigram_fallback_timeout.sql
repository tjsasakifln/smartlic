-- ============================================================
-- Migration: 20260612140000_trigram_fallback_timeout
-- Issue:     #1750 — DatalakeQuery Trigram fallback RPC
--            statement timeout (57014)
-- Purpose:   Wrapper RPC that sets SET LOCAL statement_timeout
--            before calling search_datalake_trigram_fallback.
--            The GIN trigram index scan is heavy and the default
--            statement_timeout is too low for this operation.
-- ============================================================

CREATE OR REPLACE FUNCTION public.search_datalake_trigram_fallback_with_timeout(
    p_query_term TEXT,
    p_ufs        TEXT[]  DEFAULT NULL,
    p_limit      INTEGER DEFAULT 200
)
RETURNS TABLE (
    pncp_id              TEXT,
    uf                   TEXT,
    municipio            TEXT,
    orgao_razao_social   TEXT,
    orgao_cnpj           TEXT,
    objeto_compra        TEXT,
    valor_total_estimado NUMERIC,
    modalidade_id        INTEGER,
    modalidade_nome      TEXT,
    situacao_compra      TEXT,
    data_publicacao      TIMESTAMPTZ,
    data_abertura        TIMESTAMPTZ,
    data_encerramento    TIMESTAMPTZ,
    link_pncp            TEXT,
    esfera_id            TEXT,
    ts_rank              REAL,
    sim_score            REAL
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
    -- Issue #1750: Raise statement_timeout from the default low value
    -- to 15 seconds. The GIN trigram index scan (word_similarity on
    -- ~1.5M rows of objeto_compra) is far heavier than the FTS path
    -- and routinely exceeds the configured timeout. SET LOCAL scopes
    -- this change to the current transaction only.
    SET LOCAL statement_timeout = '15000';  -- 15 seconds in ms
    RETURN QUERY
    SELECT * FROM public.search_datalake_trigram_fallback(p_query_term, p_ufs, p_limit);
END;
$$;

COMMENT ON FUNCTION public.search_datalake_trigram_fallback_with_timeout(TEXT, TEXT[], INTEGER) IS
    'Issue #1750: Wrapper around search_datalake_trigram_fallback that sets '
    'SET LOCAL statement_timeout = 15s before calling the inner function. '
    'GIN trigram index scan needs a higher timeout than the default.';

-- Restrict to service_role only (same policy as the inner function)
REVOKE ALL ON FUNCTION public.search_datalake_trigram_fallback_with_timeout(TEXT, TEXT[], INTEGER) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.search_datalake_trigram_fallback_with_timeout(TEXT, TEXT[], INTEGER) TO service_role;
