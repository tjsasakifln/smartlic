-- RPC: backfill_ibge_codes(p_mapping jsonb)
-- Receives a JSON array of {nome, uf, codigo} objects and updates
-- pncp_raw_bids.codigo_municipio_ibge for matching rows where the
-- column is currently NULL/empty.
--
-- Used by ingestion/enricher.py::enrich_pncp_ibge_codes_job().
-- Runs after each crawl wave to backfill newly ingested rows.

CREATE OR REPLACE FUNCTION public.backfill_ibge_codes(p_mapping jsonb)
RETURNS TABLE(rows_updated bigint)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
    v_total bigint := 0;
    v_item  jsonb;
BEGIN
    FOR v_item IN SELECT * FROM jsonb_array_elements(p_mapping)
    LOOP
        WITH updated AS (
            UPDATE pncp_raw_bids
            SET codigo_municipio_ibge = (v_item->>'codigo'),
                updated_at = now()
            WHERE is_active = true
              AND LOWER(municipio) = LOWER(v_item->>'nome')
              AND UPPER(uf) = UPPER(v_item->>'uf')
              AND (codigo_municipio_ibge IS NULL OR codigo_municipio_ibge = '')
            RETURNING 1
        )
        SELECT v_total + count(*) INTO v_total FROM updated;
    END LOOP;

    RETURN QUERY SELECT v_total;
END;
$$;
