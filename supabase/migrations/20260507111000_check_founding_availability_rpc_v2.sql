-- ============================================================================
-- Migration: 20260507111000_check_founding_availability_rpc_v2
-- Issue: #782 — pivot founding_policy to one-time R$997 lifetime offer
-- Date: 2026-05-07
--
-- Purpose:
--   Recreates public.check_founding_availability() adding two new output
--   columns — offer_mode and price_brl_cents — populated from the new columns
--   added in 20260507110000_founding_policy_lifetime_pivot.sql.
--
--   The route helper _check_availability() uses safe defaults so the gap
--   between migration apply and route deploy is safe:
--     offer_mode      fallback = 'lifetime'
--     price_brl_cents fallback = 99700
--
--   Returns shape is now:
--     {available, seats_remaining, seats_total, deadline_at, paused, reason,
--      offer_mode, price_brl_cents}
-- ============================================================================

BEGIN;

DROP FUNCTION IF EXISTS public.check_founding_availability();

CREATE FUNCTION public.check_founding_availability()
RETURNS TABLE (
    available           BOOLEAN,
    seats_remaining     INT,
    seats_total         INT,
    deadline_at         TIMESTAMPTZ,
    paused              BOOLEAN,
    reason              TEXT,
    offer_mode          TEXT,
    price_brl_cents     INT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_seat_limit            INT;
    v_deadline              TIMESTAMPTZ;
    v_active                BOOLEAN;
    v_paused_at             TIMESTAMPTZ;
    v_offer_mode            TEXT;
    v_price_brl_cents       INT;
    v_completed_count       INT;
BEGIN
    -- SELECT FOR UPDATE serializes concurrent callers on the policy row.
    SELECT
        seat_limit,
        deadline_at,
        active,
        paused_at,
        offer_mode,
        price_brl_cents
    INTO
        v_seat_limit,
        v_deadline,
        v_active,
        v_paused_at,
        v_offer_mode,
        v_price_brl_cents
    FROM public.founding_policy
    WHERE id = 1
    FOR UPDATE;

    IF NOT FOUND THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := 0;
        deadline_at     := NULL;
        paused          := FALSE;
        reason          := 'founding_policy_missing';
        offer_mode      := 'lifetime';
        price_brl_cents := 99700;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Hard kill switch (structural disable).
    IF NOT v_active THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := v_paused_at IS NOT NULL;
        reason          := 'founding_disabled';
        offer_mode      := v_offer_mode;
        price_brl_cents := v_price_brl_cents;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Soft pause from admin UI (operational disable).
    IF v_paused_at IS NOT NULL THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := TRUE;
        reason          := 'founding_paused';
        offer_mode      := v_offer_mode;
        price_brl_cents := v_price_brl_cents;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Deadline passed.
    IF NOW() > v_deadline THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := FALSE;
        reason          := 'founding_deadline_passed';
        offer_mode      := v_offer_mode;
        price_brl_cents := v_price_brl_cents;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Count completed founding_leads (canonical cap signal).
    SELECT COUNT(*)::INT
    INTO v_completed_count
    FROM public.founding_leads
    WHERE checkout_status = 'completed';

    IF v_completed_count >= v_seat_limit THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := FALSE;
        reason          := 'founding_cap_reached';
        offer_mode      := v_offer_mode;
        price_brl_cents := v_price_brl_cents;
        RETURN NEXT;
        RETURN;
    END IF;

    -- Available path.
    available       := TRUE;
    seats_remaining := v_seat_limit - v_completed_count;
    seats_total     := v_seat_limit;
    deadline_at     := v_deadline;
    paused          := FALSE;
    reason          := 'available';
    offer_mode      := v_offer_mode;
    price_brl_cents := v_price_brl_cents;
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.check_founding_availability() IS
    '#782 (v2): race-safe availability check for the founding cohort. '
    'Adds offer_mode and price_brl_cents to the return set. '
    'Called by GET /v1/founding/availability and POST /v1/founding/checkout.';

GRANT EXECUTE ON FUNCTION public.check_founding_availability()
    TO service_role, authenticated, anon;

NOTIFY pgrst, 'reload schema';

COMMIT;
