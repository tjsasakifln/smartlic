-- ============================================================================
-- Migration: 20260606040000_create_email_tracking_events
-- Issue: #1421 — DIGEST-005: Metrics + Mixpanel tracking for digest emails
-- Date: 2026-06-06
--
-- Purpose:
--   Track email digest events (sent, opened, clicked, unsubscribed) in a
--   dedicated table so the admin dashboard widget can query digest metrics
--   without relying on Mixpanel (external analytics).
--
-- Fields:
--   id                UUID primary key (gen_random_uuid())
--   tracking_id       UUID used in email HTML as the tracking identifier
--   event_type        TEXT CHECK: 'sent', 'opened', 'clicked', 'unsubscribed'
--   user_id           UUID referencing profiles (nullable for anonymous opens)
--   digest_frequency  Frequency: 'daily', 'twice_weekly', 'weekly'
--   metadata          JSONB for extra data (opportunity count, sectors, target URL)
--   created_at        TIMESTAMPTZ default NOW()
--
-- Permissions:
--   - service_role only (inserted by backend, queried by admin dashboard)
-- ============================================================================

BEGIN;

-- ============================================================================
-- Create the table
-- ============================================================================

CREATE TABLE IF NOT EXISTS public.email_tracking_events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tracking_id      UUID NOT NULL,
    event_type       TEXT NOT NULL CHECK (event_type IN ('sent', 'opened', 'clicked', 'unsubscribed')),
    user_id          UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    digest_frequency TEXT DEFAULT 'daily',
    metadata         JSONB DEFAULT '{}'::jsonb,
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Indexes for fast admin queries
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_email_tracking_type_time
    ON public.email_tracking_events (event_type, created_at);

CREATE INDEX IF NOT EXISTS idx_email_tracking_tracking_id
    ON public.email_tracking_events (tracking_id);

CREATE INDEX IF NOT EXISTS idx_email_tracking_user_id
    ON public.email_tracking_events (user_id);

-- ============================================================================
-- RLS: service_role only
-- ============================================================================

ALTER TABLE public.email_tracking_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY email_tracking_events_service_policy
    ON public.email_tracking_events
    USING (true)
    WITH CHECK (true);

-- ============================================================================
-- Grant permissions
-- ============================================================================

GRANT ALL ON public.email_tracking_events TO service_role;

-- ============================================================================
-- Notify PostgREST to reload schema
-- ============================================================================

NOTIFY pgrst, 'reload schema';

COMMIT;
