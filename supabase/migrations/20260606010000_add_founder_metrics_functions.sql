-- ============================================================================
-- Migration: 20260606010000_add_founder_metrics_functions
-- Issue: #1414 — FOUNDER-001: SQL queries for MRR, churn, trial-to-paid,
--   D7 retention, ARPA
-- Date: 2026-06-06
--
-- Purpose:
--   Create PostgreSQL functions that compute financial and engagement metrics
--   for the founder dashboard. All functions are STABLE (read-only).
--
-- Functions created:
--   1. get_mrr(start_date, end_date)
--      Monthly Recurring Revenue: sums active subscriptions by month, returns
--      month + MRR in BRL + subscriber count.
--
--   2. get_churn_rate_30d()
--      Rolling 30-day cancellation rate: subscriptions canceled or expired
--      in the last 30 days divided by currently active paid subscriptions.
--
--   3. get_trial_to_paid_30d()
--      Trial-to-paid conversion rate (30-day window): users who started a
--      trial 30–60 days ago and now have an active paid subscription /
--      total users who started a trial in that window.
--
--   4. get_trial_to_paid_90d()
--      Same logic, 90-day window (trials started 90–180 days ago).
--
--   5. get_d7_retention()
--      Day-7 retention: users who logged in between 7 and 8 days after
--      signup / total users who signed up more than 7 days ago.
--
--   6. get_arpa()
--      Average Revenue Per Account: current MRR / total active paid
--      subscribers.
--
-- Dependencies:
--   - public.profiles
--   - public.user_subscriptions
--   - public.plans
--   - public.plan_billing_periods
--   - public.login_activity
--
-- Performance: All functions are STABLE (read-only), use proper indexes,
--              target <200ms execution per the issue spec.
-- ============================================================================

BEGIN;

-- ============================================================================
-- 1. get_mrr(start_date, end_date)
--
-- Returns TABLE(month DATE, mrr NUMERIC, subscriber_count BIGINT)
--
-- For each calendar month in [start_date, end_date], computes:
--   - mrr (BRL): sum of monthly values for subscriptions active in that month
--   - subscriber_count: distinct paying users active in that month
--
-- MRR contribution logic:
--   - Modern plans (smartlic_pro): use plan_billing_periods.price_cents / 100
--     (price_cents is already stored as the per-month amount in cents)
--   - Legacy monthly plans: use plans.price_brl (BRL)
--   - Legacy annual plans: use plans.price_brl / 12.0
--   - Non-recurring / free plans: excluded (price_brl = 0 or plan_id in
--     exclusion list)
--
-- An active subscription in a given month must satisfy:
--   - is_active = true
--   - subscription_status IN ('active', 'trialing')
--   - starts_at <= last day of the month
--   - expires_at IS NULL OR expires_at >= first day of the month
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_mrr(start_date DATE, end_date DATE)
RETURNS TABLE(month DATE, mrr NUMERIC, subscriber_count BIGINT)
LANGUAGE sql STABLE
AS $$
  WITH months AS (
    -- Generate one row per month in the range
    SELECT generate_series(start_date, end_date, '1 month'::interval)::DATE AS month
  ),
  monthly_value AS (
    -- Pre-compute MRR contribution per subscription plan (dated-effectively constant)
    SELECT
      p.id AS plan_id,
      pbp.billing_period,
      -- per-month BRL value: prefer plan_billing_periods.price_cents / 100,
      -- fall back to plans.price_brl (normalizing annual legacy plans)
      COALESCE(
        pbp.price_cents / 100.0,
        CASE
          WHEN p.id = 'annual' THEN p.price_brl / 12.0
          WHEN p.id IN ('free', 'free_trial', 'pack_5', 'pack_10', 'pack_20', 'master') THEN 0
          ELSE p.price_brl
        END
      ) AS monthly_brl
    FROM public.plans p
    LEFT JOIN public.plan_billing_periods pbp
      ON pbp.plan_id = p.id
      
  ),
  active_subs AS (
    -- All user_subscriptions that were active during each month
    SELECT
      m.month,
      us.id AS subscription_id,
      us.user_id,
      mv.monthly_brl
    FROM months m
    JOIN public.user_subscriptions us
      ON us.is_active = true
      AND us.subscription_status IN ('active', 'trialing')
      AND us.starts_at <= (m.month + interval '1 month' - interval '1 day')::timestamptz
      AND (us.expires_at IS NULL OR us.expires_at >= m.month::timestamptz)
    JOIN monthly_value mv
      ON mv.plan_id = us.plan_id
      AND (mv.billing_period IS NULL OR mv.billing_period = COALESCE(us.billing_period, 'monthly'))
    WHERE mv.monthly_brl > 0
  )
  SELECT
    m.month,
    COALESCE(SUM(asub.monthly_brl), 0)::NUMERIC(14,2) AS mrr,
    COUNT(DISTINCT asub.user_id)::BIGINT AS subscriber_count
  FROM months m
  LEFT JOIN active_subs asub ON asub.month = m.month
  GROUP BY m.month
  ORDER BY m.month;
$$;

COMMENT ON FUNCTION public.get_mrr IS
  'FOUNDER-001: Monthly Recurring Revenue. Returns per-month MRR in BRL and '
  'subscriber count for the given date range. Excludes free/pack plans.';

-- ============================================================================
-- 2. get_churn_rate_30d()
--
-- Returns NUMERIC (percentage 0–100).
--
-- Formula:
--   (subscriptions canceled in last 30 days)
--   / (currently active paid subscriptions) * 100
--
-- A canceled subscription is one where subscription_status changed to 'canceled'
-- or 'expired' in the last 30 days (tracked by updated_at).
--
-- An active paid subscription is one with is_active = true AND
-- subscription_status IN ('active', 'trialing') AND plan_id NOT IN
-- ('free', 'free_trial', 'pack_5', 'pack_10', 'pack_20', 'master').
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_churn_rate_30d()
RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
  SELECT
    CASE
      WHEN active_count = 0 THEN 0
      ELSE ROUND((canceled_count::NUMERIC / active_count::NUMERIC) * 100, 2)
    END
  FROM (
    SELECT
      COUNT(*) FILTER (
        WHERE subscription_status IN ('canceled', 'expired')
          AND updated_at >= NOW() - INTERVAL '30 days'
      ) AS canceled_count,
      COUNT(*) FILTER (
        WHERE is_active = true
          AND subscription_status IN ('active', 'trialing')
          AND plan_id NOT IN ('free', 'free_trial', 'pack_5', 'pack_10', 'pack_20', 'master')
      ) AS active_count
    FROM public.user_subscriptions
  ) counts;
$$;

COMMENT ON FUNCTION public.get_churn_rate_30d IS
  'FOUNDER-001: Rolling 30-day churn rate (percentage). Cancellations or '
  'expirations in the last 30 days / currently active paid subscribers.';

-- ============================================================================
-- 3. get_trial_to_paid_30d()
--
-- Returns NUMERIC (percentage 0–100).
--
-- Formula:
--   users who started a trial 30–60 days ago AND now have an active paid
--   subscription / total users who started a trial 30–60 days ago * 100
--
-- "Trial start" = profiles.plan_type = 'free_trial' in the date window.
-- "Converted to paid" = has at least one user_subscriptions row with
--   is_active = true AND subscription_status IN ('active', 'trialing')
--   AND plan_id NOT IN ('free', 'free_trial').
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_trial_to_paid_30d()
RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
  WITH trial_users AS (
    SELECT p.id
    FROM public.profiles p
    WHERE p.plan_type = 'free_trial'
      AND p.created_at >= NOW() - INTERVAL '60 days'
      AND p.created_at < NOW() - INTERVAL '30 days'
  ),
  converted AS (
    SELECT DISTINCT tu.id
    FROM trial_users tu
    JOIN public.user_subscriptions us ON us.user_id = tu.id
    WHERE us.is_active = true
      AND us.subscription_status IN ('active', 'trialing')
      AND us.plan_id NOT IN ('free', 'free_trial')
  )
  SELECT
    CASE
      WHEN total_trials = 0 THEN 0
      ELSE ROUND((converted_trials::NUMERIC / total_trials::NUMERIC) * 100, 2)
    END
  FROM (
    SELECT
      (SELECT COUNT(*) FROM trial_users) AS total_trials,
      (SELECT COUNT(*) FROM converted) AS converted_trials
  ) counts;
$$;

COMMENT ON FUNCTION public.get_trial_to_paid_30d IS
  'FOUNDER-001: Trial-to-paid conversion rate (30-day window). Trials started '
  '30–60 days ago that converted / total trials started 30–60 days ago.';

-- ============================================================================
-- 4. get_trial_to_paid_90d()
--
-- Returns NUMERIC (percentage 0–100).
--
-- Same logic as get_trial_to_paid_30d, but with a 90-day window:
--   trials started 90–180 days ago.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_trial_to_paid_90d()
RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
  WITH trial_users AS (
    SELECT p.id
    FROM public.profiles p
    WHERE p.plan_type = 'free_trial'
      AND p.created_at >= NOW() - INTERVAL '180 days'
      AND p.created_at < NOW() - INTERVAL '90 days'
  ),
  converted AS (
    SELECT DISTINCT tu.id
    FROM trial_users tu
    JOIN public.user_subscriptions us ON us.user_id = tu.id
    WHERE us.is_active = true
      AND us.subscription_status IN ('active', 'trialing')
      AND us.plan_id NOT IN ('free', 'free_trial')
  )
  SELECT
    CASE
      WHEN total_trials = 0 THEN 0
      ELSE ROUND((converted_trials::NUMERIC / total_trials::NUMERIC) * 100, 2)
    END
  FROM (
    SELECT
      (SELECT COUNT(*) FROM trial_users) AS total_trials,
      (SELECT COUNT(*) FROM converted) AS converted_trials
  ) counts;
$$;

COMMENT ON FUNCTION public.get_trial_to_paid_90d IS
  'FOUNDER-001: Trial-to-paid conversion rate (90-day window). Trials started '
  '90–180 days ago that converted / total trials started 90–180 days ago.';

-- ============================================================================
-- 5. get_d7_retention()
--
-- Returns NUMERIC (percentage 0–100).
--
-- Formula:
--   users who logged in between day 7 and day 8 after signup
--   / total users who signed up more than 7 days ago * 100
--
-- "Signup" = profiles.created_at.
-- "Logged in on day 7" = at least one login_activity.logged_in_at between
--   7 and 8 days after profiles.created_at.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_d7_retention()
RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
  WITH signups AS (
    SELECT id, created_at
    FROM public.profiles
    WHERE created_at <= NOW() - INTERVAL '7 days'
  ),
  d7_logged_in AS (
    SELECT DISTINCT p.id
    FROM signups p
    JOIN public.login_activity la ON la.user_id = p.id
      AND la.logged_in_at >= p.created_at + INTERVAL '7 days'
      AND la.logged_in_at < p.created_at + INTERVAL '8 days'
  )
  SELECT
    CASE
      WHEN total_signups = 0 THEN 0
      ELSE ROUND((retained::NUMERIC / total_signups::NUMERIC) * 100, 2)
    END
  FROM (
    SELECT
      (SELECT COUNT(*) FROM signups) AS total_signups,
      (SELECT COUNT(*) FROM d7_logged_in) AS retained
  ) counts;
$$;

COMMENT ON FUNCTION public.get_d7_retention IS
  'FOUNDER-001: Day-7 retention rate (percentage). Users with a login event '
  'on day 7 after signup / all users who signed up 7+ days ago.';

-- ============================================================================
-- 6. get_arpa()
--
-- Returns NUMERIC (BRL).
--
-- Formula:
--   current MRR / total active paid subscribers
--
-- Delegates MRR calculation to get_mrr() so the formula stays consistent.
-- Active paid subscribers = count of subscriptions with is_active = true,
-- subscription_status IN ('active', 'trialing'), plan_id NOT a free/pack plan.
-- ============================================================================

CREATE OR REPLACE FUNCTION public.get_arpa()
RETURNS NUMERIC
LANGUAGE sql STABLE
AS $$
  WITH current_month AS (
    SELECT date_trunc('month', NOW())::DATE AS month_start
  ),
  mrr_data AS (
    SELECT mrr
    FROM public.get_mrr(
      (SELECT month_start FROM current_month),
      (SELECT month_start FROM current_month)
    )
  ),
  active_count AS (
    SELECT COUNT(*)::NUMERIC AS count
    FROM public.user_subscriptions us
    WHERE us.is_active = true
      AND us.subscription_status IN ('active', 'trialing')
      AND us.plan_id NOT IN ('free', 'free_trial', 'pack_5', 'pack_10', 'pack_20', 'master')
  )
  SELECT
    CASE
      WHEN (SELECT count FROM active_count) = 0 THEN 0
      ELSE ROUND(((SELECT mrr FROM mrr_data) / (SELECT count FROM active_count))::NUMERIC, 2)
    END;
$$;

COMMENT ON FUNCTION public.get_arpa IS
  'FOUNDER-001: Average Revenue Per Account (BRL). Current MRR (delegated to '
  'get_mrr) / active paid subscribers.';

-- ============================================================================
-- Grant permissions
-- ============================================================================

-- Allow service_role to execute these functions (admin dashboard)
GRANT EXECUTE ON FUNCTION public.get_mrr TO service_role;
GRANT EXECUTE ON FUNCTION public.get_churn_rate_30d TO service_role;
GRANT EXECUTE ON FUNCTION public.get_trial_to_paid_30d TO service_role;
GRANT EXECUTE ON FUNCTION public.get_trial_to_paid_90d TO service_role;
GRANT EXECUTE ON FUNCTION public.get_d7_retention TO service_role;
GRANT EXECUTE ON FUNCTION public.get_arpa TO service_role;

-- ============================================================================
-- Notify PostgREST to reload schema
-- ============================================================================

NOTIFY pgrst, 'reload schema';

COMMIT;
