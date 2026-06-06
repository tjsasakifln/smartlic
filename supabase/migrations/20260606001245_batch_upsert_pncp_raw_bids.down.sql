-- Rollback: restore original row-by-row upsert_pncp_raw_bids RPC.

DROP FUNCTION IF EXISTS public.upsert_pncp_raw_bids(JSONB) CASCADE;

CREATE OR REPLACE FUNCTION public.upsert_pncp_raw_bids(p_records JSONB)
RETURNS TABLE(inserted INT, updated INT, unchanged INT)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_record        JSONB;
    v_inserted      INT := 0;
    v_updated       INT := 0;
    v_unchanged     INT := 0;
    v_existing_hash TEXT;
    v_new_hash      TEXT;
BEGIN
    IF p_records IS NULL OR jsonb_array_length(p_records) = 0 THEN
        RETURN QUERY SELECT 0, 0, 0;
        RETURN;
    END IF;

    FOR v_record IN SELECT jsonb_array_elements(p_records)
    LOOP
        v_new_hash := v_record->>'content_hash';

        -- Fast-path: check if hash matches before attempting upsert.
        SELECT content_hash
          INTO v_existing_hash
          FROM public.pncp_raw_bids
         WHERE pncp_id = v_record->>'pncp_id';

        IF NOT FOUND THEN
            -- Record does not exist — INSERT.
            INSERT INTO public.pncp_raw_bids (
                pncp_id, objeto_compra, valor_total_estimado,
                modalidade_id, modalidade_nome, situacao_compra,
                esfera_id, uf, municipio, codigo_municipio_ibge,
                orgao_razao_social, orgao_cnpj, unidade_nome,
                data_publicacao, data_abertura, data_encerramento,
                link_sistema_origem, link_pncp, content_hash,
                ingested_at, updated_at, source, crawl_batch_id, is_active
            ) VALUES (
                v_record->>'pncp_id',
                v_record->>'objeto_compra',
                (v_record->>'valor_total_estimado')::NUMERIC,
                (v_record->>'modalidade_id')::INTEGER,
                v_record->>'modalidade_nome',
                v_record->>'situacao_compra',
                v_record->>'esfera_id',
                v_record->>'uf',
                v_record->>'municipio',
                v_record->>'codigo_municipio_ibge',
                v_record->>'orgao_razao_social',
                v_record->>'orgao_cnpj',
                v_record->>'unidade_nome',
                (v_record->>'data_publicacao')::TIMESTAMPTZ,
                (v_record->>'data_abertura')::TIMESTAMPTZ,
                (v_record->>'data_encerramento')::TIMESTAMPTZ,
                v_record->>'link_sistema_origem',
                v_record->>'link_pncp',
                v_new_hash,
                now(),
                now(),
                COALESCE(v_record->>'source', 'pncp'),
                v_record->>'crawl_batch_id',
                COALESCE((v_record->>'is_active')::BOOLEAN, true)
            );
            v_inserted := v_inserted + 1;

        ELSIF v_existing_hash IS DISTINCT FROM v_new_hash THEN
            -- Record exists and content changed — UPDATE mutable fields only.
            UPDATE public.pncp_raw_bids SET
                objeto_compra        = v_record->>'objeto_compra',
                valor_total_estimado = (v_record->>'valor_total_estimado')::NUMERIC,
                modalidade_nome      = v_record->>'modalidade_nome',
                situacao_compra      = v_record->>'situacao_compra',
                esfera_id            = v_record->>'esfera_id',
                municipio            = v_record->>'municipio',
                codigo_municipio_ibge= v_record->>'codigo_municipio_ibge',
                orgao_razao_social   = v_record->>'orgao_razao_social',
                orgao_cnpj           = v_record->>'orgao_cnpj',
                unidade_nome         = v_record->>'unidade_nome',
                data_publicacao      = (v_record->>'data_publicacao')::TIMESTAMPTZ,
                data_abertura        = (v_record->>'data_abertura')::TIMESTAMPTZ,
                data_encerramento    = (v_record->>'data_encerramento')::TIMESTAMPTZ,
                link_sistema_origem  = v_record->>'link_sistema_origem',
                link_pncp            = v_record->>'link_pncp',
                content_hash         = v_new_hash,
                updated_at           = now(),
                crawl_batch_id       = v_record->>'crawl_batch_id',
                is_active            = COALESCE((v_record->>'is_active')::BOOLEAN, true)
            WHERE pncp_id = v_record->>'pncp_id';
            v_updated := v_updated + 1;

        ELSE
            -- Hash matches — no changes, skip.
            v_unchanged := v_unchanged + 1;
        END IF;

    END LOOP;

    RETURN QUERY SELECT v_inserted, v_updated, v_unchanged;
END;
$$;

COMMENT ON FUNCTION public.upsert_pncp_raw_bids(JSONB) IS
    'Bulk upsert for PNCP bids. Skips rows where content_hash matches. '
    'SECURITY DEFINER so ingestion worker needs only EXECUTE, not table INSERT. '
    'Returns (inserted, updated, unchanged) row counts.';

GRANT EXECUTE ON FUNCTION public.upsert_pncp_raw_bids(JSONB) TO service_role;
