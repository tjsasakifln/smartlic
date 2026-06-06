-- DIGEST-001: Convert frequency from alert_frequency enum to VARCHAR(20) with CHECK
--
-- The frequency column was originally created as alert_frequency ENUM in
-- migration 20260226100000 with values (daily, twice_weekly, weekly, off).
-- This migration converts it to VARCHAR(20) for flexibility and adds a CHECK
-- constraint. The value 'off' is migrated to 'none' (DIGEST-001 naming).
--
-- Idempotent: safe to re-run. The ADD CONSTRAINT IF NOT EXISTS is emulated
-- via a DO block since PostgreSQL doesn't support IF NOT EXISTS for CHECK.

-- Step 1: Convert enum column to VARCHAR(20); migrate 'off' → 'none'
ALTER TABLE public.alert_preferences
    ALTER COLUMN frequency TYPE VARCHAR(20)
    USING CASE WHEN frequency::text = 'off' THEN 'none'
               ELSE frequency::text
          END;

-- Step 2: Add CHECK constraint (idempotent via DO block)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_alert_preferences_frequency'
          AND connamespace = 'public'::regnamespace
    ) THEN
        ALTER TABLE public.alert_preferences
            ADD CONSTRAINT chk_alert_preferences_frequency
            CHECK (frequency IN ('daily', 'twice_weekly', 'weekly', 'none'));
    END IF;
END $$;

COMMENT ON COLUMN public.alert_preferences.frequency IS
    'DIGEST-001 — Frequency for digest emails: daily, twice_weekly (mon+thu), weekly (mon), none.';
