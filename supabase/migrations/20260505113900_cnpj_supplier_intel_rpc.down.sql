-- ============================================================================
-- DOWN: cnpj_supplier_intel_rpc — reverses 20260505113900_cnpj_supplier_intel_rpc.sql
-- Date: 2026-05-05
-- Issue: #628
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   DROP RPCs `cnpj_supplier_intel(text, integer)` e `count_cnpj_contracts(text)`.
--   Operação puramente DDL (sem dados); idempotente via IF EXISTS.
--
--   IMPORTANTE: este down NÃO toca em `intel_report_purchases` — a tabela
--   reverte via 20260505113800_intel_reports_schema.down.sql (rollback granular).
-- ============================================================================

DROP FUNCTION IF EXISTS public.cnpj_supplier_intel(TEXT, INTEGER);
DROP FUNCTION IF EXISTS public.count_cnpj_contracts(TEXT);
