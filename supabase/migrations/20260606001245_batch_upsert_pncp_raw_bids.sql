-- DEBT-IO-BUDGET: Rewrite upsert_pncp_raw_bids as batch INSERT ... ON CONFLICT
-- instead of row-by-row plpgsql FOR loop.
--
-- Problem: old version looped through jsonb_to_recordset one row at a time,
-- doing SELECT-then-INSERT/UPDATE per row. Each batch of 500 records generated
-- 500-1000 individual SQL operations, consuming massive Disk IO Budget.
--
-- Solution: single INSERT ... ON CONFLICT DO UPDATE WHERE hash differs.
-- All 500 rows processed in one SQL statement, ~10x IO reduction.
--
-- Count strategy: pre-query existing pncp_ids to classify inserted vs updated.
-- unchanged = total_batch - affected.

DROP FUNCTION IF EXISTS public.upsert_pncp_raw_bids(JSONB) CASCADE;

CREATE OR REPLACE FUNCTION public.upsert_pncp_raw_bids(p_records JSONB)
RETURNS TABLE(inserted INT, updated INT, unchanged INT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_total      INT;
    v_affected   INT;
    v_inserted   INT;
    v_updated    INT;
BEGIN
    IF p_records IS NULL OR jsonb_array_length(p_records) = 0 THEN
        RETURN QUERY SELECT 0, 0, 0;
        RETURN;
    END IF;

    v_total := jsonb_array_length(p_records);

    -- Pre-check: which pncp_ids already exist (for accurate insert vs update count)
    CREATE TEMP TABLE IF NOT EXISTS _upsert_precheck (
        pncp_id       TEXT PRIMARY KEY,
        content_hash  TEXT
    ) ON COMMIT DROP;

    INSERT INTO _upsert_precheck (pncp_id, content_hash)
    SELECT b.pncp_id, b.content_hash
    FROM public.pncp_raw_bids b
    WHERE b.pncp_id IN (
        SELECT r.pncp_id
        FROM jsonb_to_recordset(p_records) AS r(pncp_id TEXT)
    );

    -- Batch upsert in a single SQL statement (no row-by-row loop)
    WITH input AS (
        SELECT
            r.pncp_id::TEXT,
            r.objeto_compra::TEXT,
            r.valor_total_estimado::NUMERIC,
            r.modalidade_id::INTEGER,
            r.modalidade_nome::TEXT,
            r.situacao_compra::TEXT,
            r.esfera_id::TEXT,
            r.uf::TEXT,
            r.municipio::TEXT,
            r.codigo_municipio_ibge::TEXT,
            r.orgao_razao_social::TEXT,
            r.orgao_cnpj::TEXT,
            r.unidade_nome::TEXT,
            r.data_publicacao::TIMESTAMPTZ,
            r.data_abertura::TIMESTAMPTZ,
            r.data_encerramento::TIMESTAMPTZ,
            r.link_sistema_origem::TEXT,
            r.link_pncp::TEXT,
            r.content_hash::TEXT,
            COALESCE(r.source::TEXT, 'pncp'),
            r.crawl_batch_id::TEXT,
            COALESCE(r.is_active::BOOLEAN, true)
        FROM jsonb_to_recordset(p_records) AS r(
            pncp_id              TEXT,
            objeto_compra        TEXT,
            valor_total_estimado NUMERIC,
            modalidade_id        INTEGER,
            modalidade_nome      TEXT,
            situacao_compra      TEXT,
            esfera_id            TEXT,
            uf                   TEXT,
            municipio            TEXT,
            codigo_municipio_ibge TEXT,
            orgao_razao_social   TEXT,
            orgao_cnpj           TEXT,
            unidade_nome         TEXT,
            data_publicacao      TIMESTAMPTZ,
            data_abertura        TIMESTAMPTZ,
            data_encerramento    TIMESTAMPTZ,
            link_sistema_origem  TEXT,
            link_pncp            TEXT,
            content_hash         TEXT,
            source               TEXT,
            crawl_batch_id       TEXT,
            is_active            BOOLEAN
        )
    ),
    upserted AS (
        INSERT INTO public.pncp_raw_bids (
            pncp_id,
            objeto_compra,
            valor_total_estimado,
            modalidade_id,
            modalidade_nome,
            situacao_compra,
            esfera_id,
            uf,
            municipio,
            codigo_municipio_ibge,
            orgao_razao_social,
            orgao_cnpj,
            unidade_nome,
            data_publicacao,
            data_abertura,
            data_encerramento,
            link_sistema_origem,
            link_pncp,
            content_hash,
            ingested_at,
            updated_at,
            source,
            crawl_batch_id,
            is_active
        )
        SELECT
            pncp_id,
            objeto_compra,
            valor_total_estimado,
            modalidade_id,
            modalidade_nome,
            situacao_compra,
            esfera_id,
            uf,
            municipio,
            codigo_municipio_ibge,
            orgao_razao_social,
            orgao_cnpj,
            unidade_nome,
            data_publicacao,
            data_abertura,
            data_encerramento,
            link_sistema_origem,
            link_pncp,
            content_hash,
            now(),
            now(),
            source,
            crawl_batch_id,
            is_active
        FROM input
        ON CONFLICT (pncp_id) DO UPDATE SET
            objeto_compra        = EXCLUDED.objeto_compra,
            valor_total_estimado = EXCLUDED.valor_total_estimado,
            modalidade_nome      = EXCLUDED.modalidade_nome,
            situacao_compra      = EXCLUDED.situacao_compra,
            esfera_id            = EXCLUDED.esfera_id,
            municipio            = EXCLUDED.municipio,
            codigo_municipio_ibge = EXCLUDED.codigo_municipio_ibge,
            orgao_razao_social   = EXCLUDED.orgao_razao_social,
            orgao_cnpj           = EXCLUDED.orgao_cnpj,
            unidade_nome         = EXCLUDED.unidade_nome,
            data_publicacao      = EXCLUDED.data_publicacao,
            data_abertura        = EXCLUDED.data_abertura,
            data_encerramento    = EXCLUDED.data_encerramento,
            link_sistema_origem  = EXCLUDED.link_sistema_origem,
            link_pncp            = EXCLUDED.link_pncp,
            content_hash         = EXCLUDED.content_hash,
            updated_at           = now(),
            crawl_batch_id       = EXCLUDED.crawl_batch_id,
            is_active            = EXCLUDED.is_active
        WHERE public.pncp_raw_bids.content_hash IS DISTINCT FROM EXCLUDED.content_hash
        RETURNING pncp_id
    )
    SELECT
        COUNT(*) FILTER (WHERE pre.pncp_id IS NULL)::INT,
        COUNT(*) FILTER (WHERE pre.pncp_id IS NOT NULL)::INT
    INTO v_inserted, v_updated
    FROM upserted u
    LEFT JOIN _upsert_precheck pre USING (pncp_id);

    -- Compute unchanged: rows not affected by the upsert
    v_unchanged := v_total - (v_inserted + v_updated);

    DROP TABLE IF EXISTS _upsert_precheck;

    RETURN QUERY SELECT
        COALESCE(v_inserted, 0),
        COALESCE(v_updated, 0),
        COALESCE(v_unchanged, 0);
END;
$$;

COMMENT ON FUNCTION public.upsert_pncp_raw_bids(JSONB) IS
    'Batch upsert for PNCP bids via INSERT ... ON CONFLICT DO UPDATE. '
    'Skips rows where content_hash matches (WHERE clause on DO UPDATE). '
    'SECURITY DEFINER so ingestion worker needs only EXECUTE. '
    'Returns (inserted, updated, unchanged) row counts. '
    'DEBT-IO-BUDGET: single-pass batch replaces row-by-row plpgsql loop.';

GRANT EXECUTE ON FUNCTION public.upsert_pncp_raw_bids(JSONB) TO service_role;
