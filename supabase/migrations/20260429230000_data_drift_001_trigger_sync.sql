-- DATA-DRIFT-001: Consolidate trial expiration canonical source
--
-- Canonical: user_subscriptions.expires_at (source-of-truth, read by quota/plan_enforcement.check_quota)
-- Mirror:    profiles.trial_expires_at  (read-only mirror, auto-synced via trigger)
--
-- Root cause memory: project_paulo_paywall_bypass_root_cause_2026_04_29
-- ADR:               docs/adr/SCHEMA-DRIFT.md (Option A canonical + mirror)
--
-- Drift mechanism prior to this fix:
--   * admin._assign_plan writes only user_subscriptions       -> profiles.trial_expires_at goes stale
--   * extend_trial_atomic RPC writes only profiles            -> user_subscriptions.expires_at unchanged
--   * check_quota reads user_subscriptions.expires_at         -> trial extensions invisible to paywall
--
-- Bounded scope (Stage 6 audit): 2 users (Paulo + 1 other).
--
-- Memory references:
--   * reference_supabase_down_sql_schema_conflict (CLI 2.x bug — stash .down.sql before db push)
--   * reference_supabase_management_api_query     (workaround if CLI rejects)
--   * feedback_schema_drift_psql_discriminator    (validate via information_schema before NOTIFY pgrst)

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Backfill profiles.trial_expires_at from canonical user_subscriptions
--    Idempotent: only updates rows where mirror diverges from canonical.
-- ---------------------------------------------------------------------------
UPDATE profiles AS p
SET trial_expires_at = us.expires_at
FROM user_subscriptions AS us
WHERE us.user_id = p.id
  AND us.is_active = TRUE
  AND us.expires_at IS NOT NULL
  AND p.trial_expires_at IS DISTINCT FROM us.expires_at;

-- ---------------------------------------------------------------------------
-- 2. Trigger function: sync canonical -> mirror after INSERT/UPDATE
--    SECURITY DEFINER so the trigger runs with table owner privileges
--    regardless of the originating role (service_role, admin, RPC caller).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION sync_trial_expires_at_from_subscriptions()
RETURNS TRIGGER AS $$
BEGIN
  -- Only sync for trial/billing-relevant statuses where expires_at matters.
  -- is_active is the equivalent flag in this schema; preserve sync on
  -- newly-created subscriptions (is_active=TRUE) and reactivations.
  IF NEW.is_active = TRUE AND NEW.expires_at IS NOT NULL THEN
    UPDATE profiles
    SET trial_expires_at = NEW.expires_at
    WHERE id = NEW.user_id
      AND (trial_expires_at IS DISTINCT FROM NEW.expires_at);
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION sync_trial_expires_at_from_subscriptions IS
  'DATA-DRIFT-001: keeps profiles.trial_expires_at mirror in sync with canonical user_subscriptions.expires_at. Memory: project_paulo_paywall_bypass_root_cause_2026_04_29';

-- ---------------------------------------------------------------------------
-- 3. Trigger: AFTER INSERT OR UPDATE OF expires_at, is_active
--    Drop first (idempotent re-run), then create.
-- ---------------------------------------------------------------------------
DROP TRIGGER IF EXISTS trg_sync_trial_expires_at ON user_subscriptions;
CREATE TRIGGER trg_sync_trial_expires_at
  AFTER INSERT OR UPDATE OF expires_at, is_active
  ON user_subscriptions
  FOR EACH ROW
  EXECUTE FUNCTION sync_trial_expires_at_from_subscriptions();

-- ---------------------------------------------------------------------------
-- 4. Update extend_trial_atomic RPC to write canonical (user_subscriptions).
--    Trigger above will mirror to profiles automatically.
--
--    Replaces version from 20260407000000_trial_extensions.sql.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION extend_trial_atomic(
  p_user_id UUID, p_condition TEXT, p_days INT, p_max_total INT
) RETURNS JSONB AS $$
DECLARE
  v_total INT;
  v_new_expires TIMESTAMPTZ;
  v_subscription_found BOOLEAN := FALSE;
BEGIN
  -- Cap check
  SELECT COALESCE(SUM(days_added), 0) INTO v_total
  FROM trial_extensions WHERE user_id = p_user_id;

  IF v_total + p_days > p_max_total THEN
    RETURN jsonb_build_object('error', 'max_extension_reached', 'total_extended', v_total);
  END IF;

  -- Audit row first (preserves UNIQUE(user_id, condition) semantics)
  INSERT INTO trial_extensions (user_id, condition, days_added)
  VALUES (p_user_id, p_condition, p_days);

  -- Write canonical first: user_subscriptions.expires_at += interval
  -- Trigger trg_sync_trial_expires_at mirrors to profiles automatically.
  UPDATE user_subscriptions
  SET expires_at = expires_at + (p_days || ' days')::INTERVAL
  WHERE user_id = p_user_id
    AND is_active = TRUE
    AND expires_at IS NOT NULL
  RETURNING expires_at INTO v_new_expires;

  IF FOUND THEN
    v_subscription_found := TRUE;
  END IF;

  -- Fallback: if no active subscription row exists (legacy state — pre
  -- billing webhook), still extend the profile mirror so the user is not
  -- blocked. Surfaced in the result so callers can detect the legacy case.
  IF NOT v_subscription_found THEN
    UPDATE profiles
    SET trial_expires_at = COALESCE(trial_expires_at, NOW()) + (p_days || ' days')::INTERVAL
    WHERE id = p_user_id
    RETURNING trial_expires_at INTO v_new_expires;
  END IF;

  RETURN jsonb_build_object(
    'days_added', p_days,
    'total_extended', v_total + p_days,
    'new_expires_at', v_new_expires,
    'canonical_updated', v_subscription_found
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

COMMENT ON FUNCTION extend_trial_atomic IS
  'DATA-DRIFT-001 v2: writes canonical user_subscriptions.expires_at (trigger mirrors to profiles). Falls back to profiles-only when no active subscription row exists (legacy state). Memory: project_paulo_paywall_bypass_root_cause_2026_04_29';

-- ---------------------------------------------------------------------------
-- 5. Reload PostgREST schema cache so RPC + trigger are visible immediately.
-- ---------------------------------------------------------------------------
NOTIFY pgrst, 'reload schema';

COMMIT;
