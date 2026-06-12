-- ============================================================================
-- Migration: 20260612120001_consolidate_leads_email_tracking
-- Issue: #1691 — Column leads.email_sent_at does not exist
-- Date: 2026-06-12
--
-- Purpose:
--   Consolidates the email tracking columns for the leads table. Two prior
--   migrations attempted to add these columns:
--     20260513125345_leads_email_tracking.sql
--     20260513150000_leads_email_tracking.sql
--   Both have identical DDL but their .down.sql reversals may have been
--   applied in production, leaving the table without the expected columns.
--
--   This migration is idempotent: ADD COLUMN IF NOT EXISTS ensures it is
--   safe to apply regardless of the current schema state.
--
--   SUPERSEDES: 20260513125345, 20260513150000
-- ============================================================================

BEGIN;

-- Add email tracking columns (idempotent)
ALTER TABLE public.leads
  ADD COLUMN IF NOT EXISTS email_sent_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS email_message_id TEXT,
  ADD COLUMN IF NOT EXISTS email_status TEXT DEFAULT 'pending';

COMMENT ON COLUMN public.leads.email_sent_at IS
  '#1691: Timestamp quando o lead magnet foi enviado. NULL = pendente.';

COMMENT ON COLUMN public.leads.email_message_id IS
  '#1691: Resend message ID para rastreamento de entrega/bounce.';

COMMENT ON COLUMN public.leads.email_status IS
  '#1691: Status do envio: pending, sent, failed, bounced, quota_exceeded.';

-- Recreate partial index (IF NOT EXISTS handles the primary case)
CREATE INDEX IF NOT EXISTS idx_leads_pending_email
  ON public.leads (captured_at)
  WHERE email_sent_at IS NULL AND email_status = 'pending';

COMMIT;
