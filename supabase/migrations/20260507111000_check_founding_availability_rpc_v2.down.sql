-- Rollback: restore check_founding_availability() to v1 shape (without offer_mode / price_brl_cents)
BEGIN;

DROP FUNCTION IF EXISTS public.check_founding_availability();

CREATE FUNCTION public.check_founding_availability()
RETURNS TABLE (
    available           BOOLEAN,
    seats_remaining     INT,
    seats_total         INT,
    deadline_at         TIMESTAMPTZ,
    paused              BOOLEAN,
    reason              TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
AS $$
DECLARE
    v_seat_limit       INT;
    v_deadline         TIMESTAMPTZ;
    v_active           BOOLEAN;
    v_paused_at        TIMESTAMPTZ;
    v_completed_count  INT;
BEGIN
    SELECT
        seat_limit,
        deadline_at,
        active,
        paused_at
    INTO
        v_seat_limit,
        v_deadline,
        v_active,
        v_paused_at
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
        RETURN NEXT;
        RETURN;
    END IF;

    IF NOT v_active THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := v_paused_at IS NOT NULL;
        reason          := 'founding_disabled';
        RETURN NEXT;
        RETURN;
    END IF;

    IF v_paused_at IS NOT NULL THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := TRUE;
        reason          := 'founding_paused';
        RETURN NEXT;
        RETURN;
    END IF;

    IF NOW() > v_deadline THEN
        available       := FALSE;
        seats_remaining := 0;
        seats_total     := v_seat_limit;
        deadline_at     := v_deadline;
        paused          := FALSE;
        reason          := 'founding_deadline_passed';
        RETURN NEXT;
        RETURN;
    END IF;

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
        RETURN NEXT;
        RETURN;
    END IF;

    available       := TRUE;
    seats_remaining := v_seat_limit - v_completed_count;
    seats_total     := v_seat_limit;
    deadline_at     := v_deadline;
    paused          := FALSE;
    reason          := 'available';
    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.check_founding_availability() IS
    'BIZ-FOUND-002: race-safe availability check for the founding cohort (v1 restored by rollback).';

GRANT EXECUTE ON FUNCTION public.check_founding_availability()
    TO service_role, authenticated, anon;

NOTIFY pgrst, 'reload schema';

COMMIT;
