-- FEEDBACK-005: Add muted + pre_mute_score columns to user_sector_affinity
-- Issue: #1439
--
-- Allows users to mute/unmute sectors. Muting forces affinity_score to 0.0
-- and saves the pre-mute value so it can be restored on unmute.

-- ============================================================================
-- Columns
-- ============================================================================

ALTER TABLE public.user_sector_affinity
  ADD COLUMN IF NOT EXISTS muted BOOLEAN NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS pre_mute_score NUMERIC(3,2);

COMMENT ON COLUMN public.user_sector_affinity.muted IS
    'FEEDBACK-005 — Whether this sector is muted by the user. Muted sectors have affinity_score forced to 0.0 but are never removed.';
COMMENT ON COLUMN public.user_sector_affinity.pre_mute_score IS
    'FEEDBACK-005 — Affinity score before muting. Restored when the user un-mutes. NULL when not muted.';
