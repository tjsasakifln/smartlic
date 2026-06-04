-- FEEDBACK-001/002: user_sector_affinity table + decay RPC
-- Issues: #1435, #1436

CREATE TABLE public.user_sector_affinity (
  user_id        UUID         NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  sector_id      VARCHAR      NOT NULL,
  affinity_score NUMERIC(3,2) NOT NULL DEFAULT 0.5,
  updated_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, sector_id),
  CONSTRAINT chk_affinity_score_range CHECK (affinity_score >= 0.0 AND affinity_score <= 1.0)
);

ALTER TABLE public.user_sector_affinity ENABLE ROW LEVEL SECURITY;

CREATE POLICY "usa_owner_all" ON public.user_sector_affinity
    FOR ALL TO authenticated
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_sector_affinity TO authenticated;
GRANT ALL ON public.user_sector_affinity TO service_role;

CREATE OR REPLACE FUNCTION public.set_user_sector_affinity_updated_at()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$ BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

CREATE TRIGGER trg_user_sector_affinity_updated_at
  BEFORE UPDATE ON public.user_sector_affinity
  FOR EACH ROW EXECUTE FUNCTION public.set_user_sector_affinity_updated_at();

CREATE OR REPLACE FUNCTION public.decay_user_sector_affinities()
RETURNS int LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp
AS $$
DECLARE affected_rows int;
BEGIN
  UPDATE public.user_sector_affinity SET affinity_score = GREATEST(0.01, affinity_score * 0.99);
  GET DIAGNOSTICS affected_rows = ROW_COUNT;
  RETURN affected_rows;
END;
$$;
