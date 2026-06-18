-- ============================================================================
-- DOWN: B2GOPS-013 (#2023) — Documentos colaborativos + templates
-- Date: 2026-06-18
-- Author: @dev
-- ============================================================================
-- Reverses the up migration: drops tables and policies.
-- ============================================================================

DROP POLICY IF EXISTS docs_select_own ON public.workspace_documentos;
DROP POLICY IF EXISTS docs_insert_own ON public.workspace_documentos;
DROP POLICY IF EXISTS docs_update_own ON public.workspace_documentos;
DROP POLICY IF EXISTS docs_delete_own ON public.workspace_documentos;

DROP INDEX IF EXISTS idx_documentos_user_id;
DROP INDEX IF EXISTS idx_documentos_tipo;

DROP TABLE IF EXISTS public.workspace_documentos;

DROP POLICY IF EXISTS templates_select_all ON public.workspace_documento_templates;

DROP TABLE IF EXISTS public.workspace_documento_templates;
