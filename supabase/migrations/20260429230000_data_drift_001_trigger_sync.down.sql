-- Rollback DATA-DRIFT-001: paywall consolidation
--
-- Restores extend_trial_atomic to its original profiles-only behavior
-- (from migration 20260407000000_trial_extensions.sql) and drops the
-- canonical -> mirror sync trigger.
--
-- NOTE: backfilled profiles.trial_expires_at values are NOT reverted —
-- the data is correct (mirrors canonical); reverting would re-introduce drift.

BEGIN;

-- 1. Drop sync trigger and function
DROP TRIGGER IF EXISTS trg_sync_trial_expires_at ON user_subscriptions;
DROP FUNCTION IF EXISTS sync_trial_expires_at_from_subscriptions();

-- 2. Restore extend_trial_atomic to original (profiles-only) version
CREATE OR REPLACE FUNCTION extend_trial_atomic(
  p_user_id UUID, p_condition TEXT, p_days INT, p_max_total INT
) RETURNS JSONB AS $$
DECLARE
  v_total INT;
  v_new_expires TIMESTAMPTZ;
BEGIN
  SELECT COALESCE(SUM(days_added), 0) INTO v_total
  FROM trial_extensions WHERE user_id = p_user_id;

  IF v_total + p_days > p_max_total THEN
    RETURN jsonb_build_object('error', 'max_extension_reached', 'total_extended', v_total);
  END IF;

  INSERT INTO trial_extensions (user_id, condition, days_added)
  VALUES (p_user_id, p_condition, p_days);

  UPDATE profiles
  SET trial_expires_at = trial_expires_at + (p_days || ' days')::INTERVAL
  WHERE id = p_user_id
  RETURNING trial_expires_at INTO v_new_expires;

  RETURN jsonb_build_object(
    'days_added', p_days,
    'total_extended', v_total + p_days,
    'new_expires_at', v_new_expires
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

NOTIFY pgrst, 'reload schema';

COMMIT;
