DROP FUNCTION IF EXISTS public.decay_user_sector_affinities();
DROP TRIGGER IF EXISTS trg_user_sector_affinity_updated_at ON public.user_sector_affinity;
DROP FUNCTION IF EXISTS public.set_user_sector_affinity_updated_at();
DROP POLICY IF EXISTS "usa_owner_all" ON public.user_sector_affinity;
DROP TABLE IF EXISTS public.user_sector_affinity CASCADE;
