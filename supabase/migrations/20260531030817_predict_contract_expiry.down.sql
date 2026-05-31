-- Down migration for PREDINT-001
-- Removes RPC, indexes, and columns added for contract expiry prediction

DROP FUNCTION IF EXISTS public.predict_contract_expiry(TEXT, TEXT, INTEGER, INTEGER);

DROP INDEX IF EXISTS idx_psc_expiry_uf_setor;
DROP INDEX IF EXISTS idx_psc_data_fim_vigencia;

-- Remove columns added for expiry prediction (IF EXISTS for idempotency)
ALTER TABLE pncp_supplier_contracts
  DROP COLUMN IF EXISTS data_fim_vigencia,
  DROP COLUMN IF EXISTS setor_classificado,
  DROP COLUMN IF EXISTS data_publicacao;
