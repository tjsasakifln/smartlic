-- ============================================================================
-- Rollback: 20260611120000_seed_cnae_mapping_gaps
-- Issue: #1652 - Remove the 11 CNAE mappings added by the up migration.
-- ============================================================================

BEGIN;

DELETE FROM public.cnae_setor_mapping
WHERE cnae_code IN ('4731', '4789', '6911', '6422', '3811', '8230', '4753', '8020', '4744', '4742', '8650')
  AND notes = 'seed 2026-06-11 ISSUE-1652';

-- Restore the original table comment
COMMENT ON TABLE public.cnae_setor_mapping IS
    'CNAE 4-digit prefix -> SmartLic sector mapping. DATA-CNAE-001.';

COMMIT;
