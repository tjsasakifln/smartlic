-- Revert: revoke the GRANT added by the forward migration.
REVOKE EXECUTE ON FUNCTION public.municipio_unaccented(pncp_raw_bids) FROM anon, authenticated;
