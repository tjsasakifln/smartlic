-- ============================================================================
-- Rollback migration: 20260606040000_create_email_tracking_events
-- Issue: #1421 — DIGEST-005: Metrics + Mixpanel tracking for digest emails
-- ============================================================================

BEGIN;

DROP TABLE IF EXISTS public.email_tracking_events;

COMMIT;
