-- FEEDBACK-005 rollback: remove muted + pre_mute_score columns

ALTER TABLE public.user_sector_affinity
  DROP COLUMN IF EXISTS muted,
  DROP COLUMN IF EXISTS pre_mute_score;
