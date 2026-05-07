-- REPO-004 rollback: drop the 9 nullable columns added for B2G reposicionamento
ALTER TABLE public.leads DROP COLUMN IF EXISTS nome;
ALTER TABLE public.leads DROP COLUMN IF EXISTS empresa;
ALTER TABLE public.leads DROP COLUMN IF EXISTS cnpj;
ALTER TABLE public.leads DROP COLUMN IF EXISTS telefone;
ALTER TABLE public.leads DROP COLUMN IF EXISTS modalidade_interesse;
ALTER TABLE public.leads DROP COLUMN IF EXISTS mensagem;
ALTER TABLE public.leads DROP COLUMN IF EXISTS utm_source;
ALTER TABLE public.leads DROP COLUMN IF EXISTS utm_campaign;
ALTER TABLE public.leads DROP COLUMN IF EXISTS referer_path;
