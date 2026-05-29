-- Computed column: accent-insensitive municipio name for PostgREST filtering.
-- PostgREST exposes functions with signature f(table_name) -> scalar as computed
-- columns, enabling .ilike("municipio_unaccented", nome) in the Python client.
-- This is the ONLY way to do accent-insensitive filtering via postgrest-py because
-- inline function expressions (unaccent(municipio)=ilike.value) are not supported
-- by the PostgREST version deployed in Supabase (returns 42703).
CREATE OR REPLACE FUNCTION public.municipio_unaccented(p pncp_raw_bids)
RETURNS text
LANGUAGE sql
IMMUTABLE
SET search_path = ''
AS $$
  SELECT public.unaccent(p.municipio);
$$;

COMMENT ON FUNCTION public.municipio_unaccented(pncp_raw_bids)
IS 'Accent-insensitive municipio name for filtering via PostgREST computed column';
