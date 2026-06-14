-- Rollback: Remove p_offset from search_datalake, reverting to TRUNC-001 behavior
-- (binary date-range splitting only, no offset-based intra-day pagination).

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
    p_limit        INTEGER           DEFAULT 2000
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
    IF p_modo NOT IN ('publicacao', 'abertas') THEN
        RAISE EXCEPTION 'p_modo must be ''publicacao'' or ''abertas'', got: %', p_modo;
    END IF;

    IF p_limit > 5000 THEN
        p_limit := 5000;
    END IF;

    IF p_tsquery IS NOT NULL AND trim(p_tsquery) <> '' THEN
        BEGIN
            v_ts_query := to_tsquery('portuguese', p_tsquery);
        EXCEPTION WHEN OTHERS THEN
            v_ts_query := plainto_tsquery('portuguese', p_tsquery);
        END;
    END IF;

    RETURN QUERY
    SELECT
        b.pncp_id, b.objeto_compra, b.valor_total_estimado,
        b.modalidade_id, b.modalidade_nome, b.situacao_compra, b.esfera_id,
        b.uf, b.municipio, b.orgao_razao_social, b.orgao_cnpj,
        b.data_publicacao, b.data_abertura, b.data_encerramento, b.link_pncp,
        CASE WHEN v_ts_query IS NOT NULL
             THEN ts_rank(b.tsv, v_ts_query)
             ELSE 0.0
        END::REAL AS ts_rank
    FROM public.pncp_raw_bids b
    WHERE
        b.is_active = true
        AND (p_ufs IS NULL       OR b.uf = ANY(p_ufs))
        AND (p_modalidades IS NULL OR b.modalidade_id = ANY(p_modalidades))
        AND (p_esferas IS NULL   OR b.esfera_id = ANY(p_esferas))
        AND (p_valor_min IS NULL OR b.valor_total_estimado >= p_valor_min)
        AND (p_valor_max IS NULL OR b.valor_total_estimado <= p_valor_max)
        AND (v_ts_query IS NULL OR b.tsv @@ v_ts_query)
        AND (p_modo <> 'publicacao'
            OR ((p_date_start IS NULL OR b.data_publicacao >= p_date_start::TIMESTAMPTZ)
                AND (p_date_end IS NULL OR b.data_publicacao < (p_date_end + INTERVAL '1 day')::TIMESTAMPTZ)))
        AND (p_modo <> 'abertas'
            OR (b.data_encerramento > now()
                AND (p_date_start IS NULL OR b.data_publicacao >= p_date_start::TIMESTAMPTZ)))
    ORDER BY
        CASE WHEN v_ts_query IS NOT NULL
             THEN ts_rank(b.tsv, v_ts_query)
             ELSE NULL
        END DESC NULLS LAST,
        b.data_publicacao DESC
    LIMIT p_limit;
END;
$$;

COMMENT ON FUNCTION public.search_datalake(TEXT[], DATE, DATE, TEXT, INTEGER[], NUMERIC, NUMERIC, TEXT[], TEXT, INTEGER) IS
    'Full-featured datalake search using pre-computed tsv column (DEBT-DB-NEW-004).';

GRANT EXECUTE ON FUNCTION public.search_datalake(TEXT[], DATE, DATE, TEXT, INTEGER[], NUMERIC, NUMERIC, TEXT[], TEXT, INTEGER) TO authenticated;
GRANT EXECUTE ON FUNCTION public.search_datalake(TEXT[], DATE, DATE, TEXT, INTEGER[], NUMERIC, NUMERIC, TEXT[], TEXT, INTEGER) TO service_role;
