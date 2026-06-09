-- Rollback GAP-008: Remove RPC, constraint, and columns
-- Order matters: dependents first → drop function → constraint → columns

DROP FUNCTION IF EXISTS upsert_supplier_contracts(jsonb);

ALTER TABLE pncp_supplier_contracts
  DROP CONSTRAINT IF EXISTS uq_psc_fornecedor_contrato_ano;

ALTER TABLE pncp_supplier_contracts
  DROP COLUMN IF EXISTS nr_contrato,
  DROP COLUMN IF EXISTS ano;
