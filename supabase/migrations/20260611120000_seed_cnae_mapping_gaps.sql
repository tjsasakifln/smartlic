-- ============================================================================
-- Migration: 20260611120000_seed_cnae_mapping_gaps
-- Issue: #1652 - CNAE mapping gaps — cobertura de setores incompleta
-- Date: 2026-06-11
--
-- Purpose:
--   Seeds 11 new CNAE -> sector mappings for codes that were frequently
--   hitting the "cnae_not_mapped" warning in production logs, causing
--   fallback to "geral" (general sector).
--
--   See backend/utils/cnae_mapping.py for the hardcoded fallback dict
--   which MUST be kept in sync with this seed.
-- ============================================================================

BEGIN;

INSERT INTO public.cnae_setor_mapping (cnae_code, setor_id, notes) VALUES
    ('4731', 'frota_veicular',     'seed 2026-06-11 ISSUE-1652'),
    ('4789', 'papelaria',          'seed 2026-06-11 ISSUE-1652'),
    ('6911', 'servicos_prediais',   'seed 2026-06-11 ISSUE-1652'),
    ('6422', 'informatica',        'seed 2026-06-11 ISSUE-1652'),
    ('3811', 'servicos_prediais',   'seed 2026-06-11 ISSUE-1652'),
    ('8230', 'servicos_prediais',   'seed 2026-06-11 ISSUE-1652'),
    ('4753', 'vestuario',          'seed 2026-06-11 ISSUE-1652'),
    ('8020', 'vigilancia',         'seed 2026-06-11 ISSUE-1652'),
    ('4744', 'engenharia',         'seed 2026-06-11 ISSUE-1652'),
    ('4742', 'mobiliario',         'seed 2026-06-11 ISSUE-1652'),
    ('8650', 'saude',              'seed 2026-06-11 ISSUE-1652')
ON CONFLICT (cnae_code) DO NOTHING;

-- Update coverage comment in the table
COMMENT ON TABLE public.cnae_setor_mapping IS
    'CNAE 4-digit prefix -> SmartLic sector mapping. DATA-CNAE-001. 70 entries as of 2026-06-11 (ISSUE-1652).';

COMMIT;
