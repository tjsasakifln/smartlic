-- ============================================================================
-- DOWN: Removes leads email tracking columns
-- Reverses: 20260612120001_consolidate_leads_email_tracking.sql
-- Date: 2026-06-12
-- ============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_leads_pending_email;

ALTER TABLE public.leads
  DROP COLUMN IF EXISTS email_sent_at,
  DROP COLUMN IF EXISTS email_message_id,
  DROP COLUMN IF EXISTS email_status;

COMMIT;
