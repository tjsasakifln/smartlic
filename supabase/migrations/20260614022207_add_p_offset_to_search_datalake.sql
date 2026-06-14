-- ============================================================================
-- TRUNC-002: Add p_offset parameter to search_datalake RPC.
--
-- When binary date-range splitting reaches single-day granularity and the
-- UF (e.g. SP) still has >1000 rows per day, the PostgREST hard cap cannot
-- be avoided with date splits alone.  Adding p_offset allows the Python
-- pagination layer to fetch all rows via offset-based batching.
--
-- Fixes: #1746 — UF=SP truncation, 147s query, 1000-row cap exceeded
-- ============================================================================

CREATE OR REPLACE FUNCTION public.search_datalake(
    p_ufs          TEXT[]            DEFAULT NULL,
    p_date_start   DATE              DEFAULT NULL,
    p_date_end     DATE              DEFAULT NULL,
    p_tsquery      TEXT              DEFAULT NULL,
    p_modalidades  INTEGER[]         DEFAULT NULL,
    p_valor_min    NUMERIC           DEFAULT NULL,
    p_valor_max    NUMERIC           DEFAULT NULL,
    p_esferas      TEXT[]            DEFAULT NULL,
    p_modo         TEXT              DEFAULT 'publicacao',
    p_limit        INTEGER           DEFAULT 2000,
    p_offset       INTEGER           DEFAULT 0
)
RETURNS TABLE (
    pncp_id              TEXT,
    objeto_compra        TEXT,
    valor_total_estimado NUMERIC,
    modalidade_id        INTEGER,
    modalidade_nome      TEXT,
    situacao_compra      TEXT,
    esfera_id            TEXT,
    uf                   TEXT,
    municipio            TEXT,
    orgao_razao_social   TEXT,
    orgao_cnpj           TEXT,
    data_publicacao      TIMESTAMPTZ,
    data_abertura        TIMESTAMPTZ,
    data_encerramento    TIMESTAMPTZ,
    link_pncp            TEXT,
    ts_rank              REAL
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_ts_query TSQUERY;
BEGIN
    -- Validate modo parameter.
    IF p_modo NOT IN ('publicacao', 'abertas') THEN
        RAISE EXCEPTION 'p_modo must be ''publicacao'' or ''abertas'', got: %', p_modo;
    END IF;

    -- Cap limit to prevent runaway queries.
    IF p_limit > 5000 THEN
        p_limit := 5000;
    END IF;

    -- Parse tsquery once; NULL means no full-text filter.
    IF p_tsquery IS NOT NULL AND trim(p_tsquery) <> '' THEN
        BEGIN
            v_ts_query := to_tsquery('portuguese', p_tsquery);
        EXCEPTION WHEN OTHERS THEN
            -- Malformed tsquery — fallback to plain text search.
            v_ts_query := plainto_tsquery('portuguese', p_tsquery);
        END;
    END IF;

    RETURN QUERY
    SELECT
        b.pncp_id,
        b.objeto_compra,
        b.valor_total_estimado,
        b.modalidade_id,
        b.modalidade_nome,
        b.situacao_compra,
        b.esfera_id,
        b.uf,
        b.municipio,
        b.orgao_razao_social,
        b.orgao_cnpj,
        b.data_publicacao,
        b.data_abertura,
        b.data_encerramento,
        b.link_pncp,
        -- ts_rank uses pre-computed tsv column (no recomputation).
        CASE
            WHEN v_ts_query IS NOT NULL
            THEN ts_rank(b.tsv, v_ts_query)
            ELSE 0.0
        END::REAL AS ts_rank
    FROM public.pncp_raw_bids b
    WHERE
        b.is_active = true

        -- UF filter: pass NULL to include all UFs.
        AND (p_ufs IS NULL       OR b.uf = ANY(p_ufs))

        -- Modality filter: pass NULL to include all modalities.
        AND (p_modalidades IS NULL OR b.modalidade_id = ANY(p_modalidades))

        -- Government sphere filter.
        AND (p_esferas IS NULL   OR b.esfera_id = ANY(p_esferas))

        -- Value range filters (inclusive).
        AND (p_valor_min IS NULL OR b.valor_total_estimado >= p_valor_min)
        AND (p_valor_max IS NULL OR b.valor_total_estimado <= p_valor_max)

        -- Full-text match using pre-computed tsv column (GIN indexed).
        AND (
            v_ts_query IS NULL
            OR b.tsv @@ v_ts_query
        )

        -- Date mode: 'publicacao' filters by publication date window.
        AND (
            p_modo <> 'publicacao'
            OR (
                (p_date_start IS NULL OR b.data_publicacao >= p_date_start::TIMESTAMPTZ)
                AND
                (p_date_end   IS NULL OR b.data_publicacao <  (p_date_end + INTERVAL '1 day')::TIMESTAMPTZ)
            )
        )

        -- Date mode: 'abertas' — encerramento in the future, publicacao >= start.
        AND (
            p_modo <> 'abertas'
            OR (
                b.data_encerramento > now()
                AND (p_date_start IS NULL OR b.data_publicacao >= p_date_start::TIMESTAMPTZ)
            )
        )

    ORDER BY
        -- When full-text query supplied, rank by relevance first.
        CASE WHEN v_ts_query IS NOT NULL
             THEN ts_rank(b.tsv, v_ts_query)
             ELSE NULL
        END DESC NULLS LAST,
        b.data_publicacao DESC

    LIMIT p_limit OFFSET p_offset;
END;
$$;

COMMENT ON FUNCTION public.search_datalake(TEXT[], DATE, DATE, TEXT, INTEGER[], NUMERIC, NUMERIC, TEXT[], TEXT, INTEGER, INTEGER) IS
    'Full-featured datalake search with offset pagination support (TRUNC-002).'
    ' p_offset=0 → first page; p_offset=1000 → next page. Used for UF=SP overflow when single-day rows exceed PostgREST 1000-row cap.';

-- Permissions: match previous grants
GRANT EXECUTE ON FUNCTION public.search_datalake(TEXT[], DATE, DATE, TEXT, INTEGER[], NUMERIC, NUMERIC, TEXT[], TEXT, INTEGER, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION public.search_datalake(TEXT[], DATE, DATE, TEXT, INTEGER[], NUMERIC, NUMERIC, TEXT[], TEXT, INTEGER, INTEGER) TO service_role;
