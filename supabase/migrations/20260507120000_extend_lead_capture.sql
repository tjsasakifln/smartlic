-- REPO-004: Extend leads table for B2G reposicionamento diagnostic form
-- Adds 9 nullable columns; fully backward-compatible (no NOT NULL, no default changes)
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS nome TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS empresa TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS cnpj TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS telefone TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS modalidade_interesse TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS mensagem TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS utm_source TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS utm_campaign TEXT;
ALTER TABLE public.leads ADD COLUMN IF NOT EXISTS referer_path TEXT;

-- Optional: document valid source values via a comment (constraint already enforced at API layer)
COMMENT ON COLUMN public.leads.modalidade_interesse IS 'radar | report | intel | nao_sei';
