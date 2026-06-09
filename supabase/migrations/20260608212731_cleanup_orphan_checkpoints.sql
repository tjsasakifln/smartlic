-- GAP-007: Cleanup orphan checkpoints — weekly pg_cron
--
-- Creates a function that deletes ingestion_checkpoints rows whose UF
-- is no longer in the active 27-UF list. This prevents accumulation of
-- stale checkpoint records when a UF is removed from the crawl config.
--
-- The function is meant to be called by a weekly pg_cron job (see
-- 20260608212732_cleanup_orphan_checkpoints_schedule.sql) but can also
-- be invoked manually:
--
--   SELECT cleanup_orphan_checkpoints();
--
-- Returns the number of deleted rows.
--
-- ============================================================================

CREATE OR REPLACE FUNCTION public.cleanup_orphan_checkpoints()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    v_deleted INTEGER;
BEGIN
    DELETE FROM public.ingestion_checkpoints
    WHERE uf NOT IN (
        'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO',
        'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR',
        'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO'
    );

    GET DIAGNOSTICS v_deleted = ROW_COUNT;

    RETURN v_deleted;
END;
$$;

COMMENT ON FUNCTION public.cleanup_orphan_checkpoints() IS
    'GAP-007: Deletes ingestion_checkpoints rows whose UF is not in the active 27-UF list. Returns count of deleted rows.';

NOTIFY pgrst, 'reload schema';
