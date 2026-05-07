BEGIN;

ALTER TABLE public.founding_policy
    ADD COLUMN IF NOT EXISTS offer_mode TEXT NOT NULL DEFAULT 'lifetime'
        CHECK (offer_mode IN ('subscription', 'lifetime')),
    ADD COLUMN IF NOT EXISTS price_brl_cents INT NOT NULL DEFAULT 99700
        CHECK (price_brl_cents > 0),
    ADD COLUMN IF NOT EXISTS consulting_discount_pct INT NOT NULL DEFAULT 50
        CHECK (consulting_discount_pct >= 0 AND consulting_discount_pct <= 100);

UPDATE public.founding_policy
SET deadline_at = '2026-06-30T23:59:59-03:00'::TIMESTAMPTZ,
    offer_mode = 'lifetime',
    price_brl_cents = 99700,
    consulting_discount_pct = 50
WHERE id = 1;

NOTIFY pgrst, 'reload schema';

COMMIT;
