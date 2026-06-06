-- DIGEST-001: Rollback — revert frequency to alert_frequency enum.
-- Ensure the alert_frequency type still exists (recreated if necessary).

-- Step 1: Drop CHECK constraint
ALTER TABLE public.alert_preferences DROP CONSTRAINT IF EXISTS chk_alert_preferences_frequency;

-- Step 2: Recreate the enum type if it was dropped (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'alert_frequency'
    ) THEN
        CREATE TYPE alert_frequency AS ENUM ('daily', 'twice_weekly', 'weekly', 'off');
    END IF;
END $$;

-- Step 3: Convert VARCHAR(20) back to alert_frequency; migrate 'none' → 'off'
ALTER TABLE public.alert_preferences
    ALTER COLUMN frequency TYPE alert_frequency
    USING CASE WHEN frequency::text = 'none' THEN 'off'::alert_frequency
               ELSE frequency::text::alert_frequency
          END;

-- Step 4: Restore comment
COMMENT ON COLUMN public.alert_preferences.frequency IS
    'Frequency for digest emails: daily, twice_weekly, weekly, off.';
