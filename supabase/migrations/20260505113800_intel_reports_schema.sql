-- ============================================================================
-- UP: intel_reports_schema — INTEL-REPORT-001 "Raio-X do Concorrente"
-- Date: 2026-05-05
-- Issue: #628
-- Author: @data-engineer
-- ============================================================================
-- Context:
--   Primeiro produto one-time purchase da plataforma (R$197). Esta migration
--   cria a tabela `intel_report_purchases` que rastreia o ciclo de vida de
--   compras de relatórios PDF: pending → generating → ready (ou failed/refunded).
--   PDFs expiram após 30 dias (signed URL).
--
--   RPCs `cnpj_supplier_intel` e `count_cnpj_contracts` são adicionadas em
--   migration separada (20260505113900_cnpj_supplier_intel_rpc.sql) para
--   permitir rollback granular do schema vs lógica de agregação.
-- ============================================================================

BEGIN;

-- ────────────────────────────────────────────────────────────────────────────
-- Tabela: intel_report_purchases
-- ────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS public.intel_report_purchases (
    id                          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID         NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    product_type                TEXT         NOT NULL,
    entity_key                  TEXT         NOT NULL,                       -- e.g. CNPJ for raio-x
    stripe_payment_intent_id    TEXT         UNIQUE,                          -- Stripe pi_xxx
    status                      TEXT         NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending','generating','ready','failed','refunded')),
    pdf_url                     TEXT,                                         -- signed URL (Supabase Storage)
    created_at                  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    expires_at                  TIMESTAMPTZ  NOT NULL DEFAULT (NOW() + INTERVAL '30 days')
);

COMMENT ON TABLE  public.intel_report_purchases IS
    'INTEL-REPORT-001 — One-time PDF report purchases (R$197 raio-x do concorrente). 30d signed URL expiry.';
COMMENT ON COLUMN public.intel_report_purchases.product_type IS
    'Tipo de relatório (ex.: cnpj_raio_x). Permite expansão futura sem schema change.';
COMMENT ON COLUMN public.intel_report_purchases.entity_key IS
    'Chave da entidade analisada — para cnpj_raio_x é o CNPJ (digits-only).';
COMMENT ON COLUMN public.intel_report_purchases.stripe_payment_intent_id IS
    'Idempotency key contra Stripe webhook. UNIQUE evita double-fulfillment.';
COMMENT ON COLUMN public.intel_report_purchases.status IS
    'Lifecycle: pending → generating → ready | failed | refunded.';

-- ────────────────────────────────────────────────────────────────────────────
-- Índices
-- ────────────────────────────────────────────────────────────────────────────

-- Lookup principal: relatórios de um usuário (página "Meus Relatórios")
CREATE INDEX IF NOT EXISTS idx_irp_user_id
    ON public.intel_report_purchases (user_id, created_at DESC);

-- Webhook Stripe lookup por payment_intent (já é UNIQUE, mas índice explícito
-- para clareza e plan stability)
CREATE INDEX IF NOT EXISTS idx_irp_stripe_pi
    ON public.intel_report_purchases (stripe_payment_intent_id);

-- Worker que polla relatórios em estado 'generating' (job de PDF generation)
CREATE INDEX IF NOT EXISTS idx_irp_status
    ON public.intel_report_purchases (status, created_at DESC);

-- ────────────────────────────────────────────────────────────────────────────
-- RLS: SELECT restrito a auth.uid() = user_id; writes apenas via service_role.
-- ────────────────────────────────────────────────────────────────────────────

ALTER TABLE public.intel_report_purchases ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "irp_owner_select"     ON public.intel_report_purchases;
DROP POLICY IF EXISTS "irp_service_insert"   ON public.intel_report_purchases;
DROP POLICY IF EXISTS "irp_service_update"   ON public.intel_report_purchases;
DROP POLICY IF EXISTS "irp_service_select"   ON public.intel_report_purchases;

-- Authenticated users see only their own purchases
CREATE POLICY "irp_owner_select" ON public.intel_report_purchases
    FOR SELECT
    TO authenticated
    USING (auth.uid() = user_id);

-- service_role precisa SELECT/INSERT/UPDATE para webhook + worker
CREATE POLICY "irp_service_select" ON public.intel_report_purchases
    FOR SELECT
    TO service_role
    USING (true);

CREATE POLICY "irp_service_insert" ON public.intel_report_purchases
    FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "irp_service_update" ON public.intel_report_purchases
    FOR UPDATE
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Note: anon e authenticated NÃO recebem INSERT/UPDATE — apenas service_role.
-- DELETE não é exposto a ninguém (relatórios são histórico financeiro,
-- preservados; refunded é status, não delete).

COMMIT;
