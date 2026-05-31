-- Fix: migration 20260529183000 created municipio_unaccented(pncp_raw_bids)
-- but did not GRANT EXECUTE to the roles that PostgREST uses (anon, authenticated).
-- Without this grant, PostgREST cannot resolve the computed column and returns
-- 42703: "column pncp_raw_bids.unaccent(municipio) does not exist".
--
-- Root cause: the computed-column mechanism requires that the function is
-- callable by the request role.  Public SEO routes (municipios_publicos.py)
-- use the anon role, so GRANT EXECUTE is mandatory.
GRANT EXECUTE ON FUNCTION public.municipio_unaccented(pncp_raw_bids) TO anon, authenticated;

-- Refresh PostgREST schema cache so the computed column becomes visible
-- without waiting for the next automatic reload.
NOTIFY pgrst, 'reload schema';
