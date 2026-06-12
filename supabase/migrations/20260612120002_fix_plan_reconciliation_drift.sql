-- ============================================================================
-- Migration: 20260612120002_fix_plan_reconciliation_drift
-- Issue: #1692 — DEBT-010: Plan reconciliation drift
-- Date: 2026-06-12
--
-- Purpose:
--   Fixes existing plan_type mismatches between profiles and
--   user_subscriptions. This is a one-time fix for production data;
--   ongoing drift detection and auto-healing is handled by
--   run_plan_reconciliation() in backend/jobs/cron/billing.py.
--
--   This migration:
--   1. Updates profiles.plan_type to match the active subscription
--      when they disagree (profiles_stale direction).
--   2. Resets orphan profiles (paid plan but no active subscription)
--      to free_trial.
--
--   NOTE: This ONLY corrects the current state. The backend auto-heal
--   will handle any future drift going forward.
-- ============================================================================

BEGIN;

-- Fix 1: profiles_stale — profiles.plan_type != user_subscriptions.plan_id
-- for users with an active subscription
UPDATE public.profiles p
SET plan_type = us.plan_id
FROM public.user_subscriptions us
WHERE us.user_id = p.id
  AND us.is_active = TRUE
  AND p.plan_type IS DISTINCT FROM us.plan_id;

-- Fix 2: orphan_profile — profile has a paid/active plan but no
-- active subscription (reset to free_trial)
UPDATE public.profiles p
SET plan_type = 'free_trial'
WHERE p.plan_type NOT IN ('free_trial', 'cancelled', 'none')
  AND NOT EXISTS (
    SELECT 1 FROM public.user_subscriptions us
    WHERE us.user_id = p.id AND us.is_active = TRUE
  );

COMMIT;
