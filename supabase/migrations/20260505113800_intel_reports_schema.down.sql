-- ============================================================================
-- DOWN: intel_reports_schema — reverses 20260505113800_intel_reports_schema.sql
-- Date: 2026-05-05
-- Issue: #628
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Reverse criação de `intel_report_purchases` (tabela + RLS + índices).
--   IMPORTANTE: aplicar este down também desfaz qualquer compra registrada —
--   só rodar em recovery após confirmar que não há linhas, ou após backup.
--
--   Este down NÃO toca em `cnpj_supplier_intel` / `count_cnpj_contracts`
--   (RPCs vivem em migration separada com seu próprio .down.sql).
-- ============================================================================

-- DROP em ordem oposta da up; CASCADE remove policies + índices automaticamente.
-- IF EXISTS garante idempotência.

DROP POLICY IF EXISTS "irp_owner_select"   ON public.intel_report_purchases;
DROP POLICY IF EXISTS "irp_service_insert" ON public.intel_report_purchases;
DROP POLICY IF EXISTS "irp_service_update" ON public.intel_report_purchases;
DROP POLICY IF EXISTS "irp_service_select" ON public.intel_report_purchases;

DROP INDEX IF EXISTS public.idx_irp_user_id;
DROP INDEX IF EXISTS public.idx_irp_stripe_pi;
DROP INDEX IF EXISTS public.idx_irp_status;

DROP TABLE IF EXISTS public.intel_report_purchases CASCADE;
