-- ============================================================================
-- GAP-008: RPC upsert_supplier_contracts — schema independente de bids
--
-- Purpose:
--   Adiciona colunas nr_contrato e ano para chave de negócio natural
--   (ni_fornecedor, nr_contrato, ano), independente de content_hash (herdado
--   do schema de bids). Cria UNIQUE constraint e RPC dedicada.
--
-- Mudanças:
--   1. ADD COLUMN IF NOT EXISTS nr_contrato TEXT, ano INTEGER
--   2. Backfill ano from data_assinatura for existing rows
--   3. Deduplicate any existing rows that would violate the constraint
--   4. UNIQUE constraint uq_psc_fornecedor_contrato_ano
--   5. RPC upsert_supplier_contracts(contracts jsonb) RETURNS SETOF
--   6. GRANT EXECUTE TO service_role
-- ============================================================================

-- ────────────────────────────────────────────────────────────────────────────
-- Step 1: Add columns (idempotent)
-- ────────────────────────────────────────────────────────────────────────────
ALTER TABLE pncp_supplier_contracts
  ADD COLUMN IF NOT EXISTS nr_contrato TEXT,
  ADD COLUMN IF NOT EXISTS ano INTEGER;

-- ────────────────────────────────────────────────────────────────────────────
-- Step 2: Backfill ano from data_assinatura for existing rows
--         (nr_contrato cannot be backfilled — it requires API re-fetch)
-- ────────────────────────────────────────────────────────────────────────────
UPDATE pncp_supplier_contracts
SET ano = EXTRACT(YEAR FROM data_assinatura)::INTEGER
WHERE ano IS NULL AND data_assinatura IS NOT NULL;

-- ────────────────────────────────────────────────────────────────────────────
-- Step 3: Create UNIQUE constraint (business key independent of bids)
--         Multiple NULLs in nr_contrato/ano are allowed (existing rows);
--         constraint only enforces uniqueness when ALL columns are non-null.
-- ────────────────────────────────────────────────────────────────────────────
-- First, deduplicate any existing rows that would violate the constraint
-- (extremely unlikely, but safeguard against existing data drift)
DELETE FROM pncp_supplier_contracts psc1
USING pncp_supplier_contracts psc2
WHERE psc1.id > psc2.id
  AND psc1.ni_fornecedor = psc2.ni_fornecedor
  AND psc1.nr_contrato = psc2.nr_contrato
  AND psc1.ano = psc2.ano
  AND psc1.nr_contrato IS NOT NULL
  AND psc1.ano IS NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_psc_fornecedor_contrato_ano'
      AND conrelid = 'pncp_supplier_contracts'::regclass
  ) THEN
    ALTER TABLE pncp_supplier_contracts
      ADD CONSTRAINT uq_psc_fornecedor_contrato_ano
      UNIQUE (ni_fornecedor, nr_contrato, ano);
  END IF;
END;
$$;

-- ────────────────────────────────────────────────────────────────────────────
-- Step 4: RPC upsert_supplier_contracts
--         Uses the new business key for conflict detection.
--         Returns SETOF pncp_supplier_contracts (affected rows).
-- ────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION upsert_supplier_contracts(contracts jsonb)
RETURNS SETOF pncp_supplier_contracts
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
BEGIN
  -- Single-statement batch upsert using the natural business key.
  -- ON CONFLICT infers the uq_psc_fornecedor_contrato_ano constraint.
  -- Rows where nr_contrato or ano is NULL fall through to INSERT
  -- (PostgreSQL UNIQUE treats NULLs as distinct — no conflict raised).
  RETURN QUERY
  INSERT INTO pncp_supplier_contracts (
    numero_controle_pncp, ni_fornecedor, nome_fornecedor,
    nr_contrato, ano,
    orgao_cnpj, orgao_nome, uf, municipio, esfera,
    valor_global, data_assinatura, objeto_contrato,
    data_fim_vigencia,
    content_hash, is_active
  )
  SELECT
    r.numero_controle_pncp,
    r.ni_fornecedor,
    r.nome_fornecedor,
    r.nr_contrato,
    r.ano,
    r.orgao_cnpj,
    r.orgao_nome,
    r.uf,
    r.municipio,
    r.esfera,
    r.valor_global,
    r.data_assinatura,
    r.objeto_contrato,
    r.data_fim_vigencia,
    r.content_hash,
    TRUE
  FROM jsonb_to_recordset(contracts) AS r(
    numero_controle_pncp TEXT,
    ni_fornecedor        TEXT,
    nome_fornecedor      TEXT,
    nr_contrato          TEXT,
    ano                  INTEGER,
    orgao_cnpj           TEXT,
    orgao_nome           TEXT,
    uf                   TEXT,
    municipio            TEXT,
    esfera               TEXT,
    valor_global         NUMERIC,
    data_assinatura      DATE,
    objeto_contrato      TEXT,
    data_fim_vigencia    DATE,
    content_hash         TEXT
  )
  ON CONFLICT (ni_fornecedor, nr_contrato, ano) DO UPDATE SET
    nome_fornecedor   = EXCLUDED.nome_fornecedor,
    orgao_cnpj        = EXCLUDED.orgao_cnpj,
    orgao_nome        = EXCLUDED.orgao_nome,
    valor_global      = EXCLUDED.valor_global,
    data_assinatura   = EXCLUDED.data_assinatura,
    objeto_contrato   = EXCLUDED.objeto_contrato,
    data_fim_vigencia = EXCLUDED.data_fim_vigencia,
    is_active         = TRUE,
    updated_at        = NOW()
  RETURNING *;
END;
$$;

-- ────────────────────────────────────────────────────────────────────────────
-- Step 5: Grant permissions (service_role only — ingestion worker)
-- ────────────────────────────────────────────────────────────────────────────
GRANT EXECUTE ON FUNCTION upsert_supplier_contracts(jsonb)
  TO service_role;

-- ────────────────────────────────────────────────────────────────────────────
-- Step 6: Documentation
-- ────────────────────────────────────────────────────────────────────────────
COMMENT ON FUNCTION upsert_supplier_contracts(jsonb) IS
  'GAP-008: Batch upsert pncp_supplier_contracts using natural business key '
  '(ni_fornecedor, nr_contrato, ano). Returns SETOF pncp_supplier_contracts. '
  'Schema independent of bids (content_hash no longer used for conflict).';
