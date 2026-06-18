-- #2039: Disk IO Budget — índices compostos para queries frequentes
-- Wave 1: Alívio imediato — índices faltantes identificados por análise de query patterns.
--
-- Contexto: queries que filtram por múltiplas colunas sem índice composto adequado
-- forçam o Postgres a fazer index scan + filter sequencial, multiplicando IO por query.

-- ============================================================================
-- 1. workspace_timeline_eventos — composite index (edital_id, user_id, created_at DESC)
-- ============================================================================
-- Query pattern: .eq("edital_id", X).eq("user_id", Y).order("created_at", desc=True)
-- O índice existente idx_timeline_eventos_edital cobre (edital_id, created_at DESC)
-- mas o filter por user_id força um filtro adicional pós-index scan.
-- Com o composite index, o Postgres resolve edital_id + user_id + ORDER BY em um acesso.
CREATE INDEX IF NOT EXISTS idx_timeline_eventos_edital_user_created
    ON workspace_timeline_eventos(edital_id, user_id, created_at DESC);

-- ============================================================================
-- 2. workspace_documentos — composite index (user_id, created_at DESC)
-- ============================================================================
-- Query pattern esperado: listagem de docs por usuário com ordenação cronológica.
-- O índice idx_documentos_user_id cobre user_id, mas sem ordenação.
CREATE INDEX IF NOT EXISTS idx_documentos_user_created
    ON workspace_documentos(user_id, created_at DESC);

-- ============================================================================
-- 3. outgoing_webhook_deliveries — partial index para retries pendentes
-- ============================================================================
-- Query pattern: worker de retry busca deliveries com status='pending'
-- E next_retry_at <= NOW(). O índice existente idx_outgoing_webhook_pending
-- cobre next_retry_at WHERE status='pending', mas sem incluir a condição
-- de tempo. Adicionar índice com INCLUDE reduz lookup de colunas adicionais.
-- (Nota: INCLUDE só funciona em PG 11+ — Supabase usa PG 17)
CREATE INDEX IF NOT EXISTS idx_outgoing_webhook_retry_due
    ON outgoing_webhook_deliveries(next_retry_at, channel)
    WHERE status = 'pending' AND next_retry_at IS NOT NULL;

-- ============================================================================
-- 4. search_results_cache — índice para queries do alert_engine
-- ============================================================================
-- O alert_engine consulta search_results_cache com .gte("created_at", since) SEM
-- filtro de user_id. O índice idx_search_cache_user começa com user_id → inútil aqui.
-- Este índice cobre a query de janela temporal do alert_engine.
CREATE INDEX IF NOT EXISTS idx_search_cache_created_at
    ON search_results_cache(created_at DESC);

-- Índice para queries user-scoped com INCLUDE para evitar heap lookup.
-- O alert_engine busca search_params + results por user_id.
CREATE INDEX IF NOT EXISTS idx_search_cache_user_params
    ON search_results_cache(user_id, created_at DESC)
    INCLUDE (search_params, results);
