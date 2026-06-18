-- Rollback para 20260618120000_disk_io_budget_indexes.sql
-- Issue #2039: Remove os índices adicionados na Wave 1

DROP INDEX IF EXISTS idx_timeline_eventos_edital_user_created;
DROP INDEX IF EXISTS idx_documentos_user_created;
DROP INDEX IF EXISTS idx_outgoing_webhook_retry_due;
DROP INDEX IF EXISTS idx_search_cache_created_at;
DROP INDEX IF EXISTS idx_search_cache_user_params;
