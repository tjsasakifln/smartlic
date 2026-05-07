BEGIN;

ALTER TABLE public.founding_policy
    DROP COLUMN IF EXISTS offer_mode,
    DROP COLUMN IF EXISTS price_brl_cents,
    DROP COLUMN IF EXISTS consulting_discount_pct;

NOTIFY pgrst, 'reload schema';

COMMIT;
