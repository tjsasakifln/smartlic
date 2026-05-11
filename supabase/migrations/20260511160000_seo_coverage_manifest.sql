-- SEO-COVERAGE-MANIFEST-001: Tabela de cobertura de dados para sitemap gate
--
-- Motivação: o sitemap emite ~10k URLs sem garantia de cobertura mínima.
-- Municípios (lista hardcoded) e outros slugs podem renderizar EmptyState,
-- desperdiçando crawl budget. Esta tabela é a fonte-de-verdade centralizada
-- para cobertura por entidade.
--
-- coverage_status values:
--   full            — slug tem dados recentes (<= 6 meses)
--   partial         — slug tem dados mas antigos (6-24 meses)
--   historical_empty— slug teve dados mas não tem nos últimos 24 meses
--   empty           — slug nunca teve dados conhecidos
--
-- Populada diariamente pelo cron seo_coverage_manifest_job (3am BRT / 6h UTC).

CREATE TABLE IF NOT EXISTS seo_coverage_manifest (
    entity_type  TEXT        NOT NULL,  -- 'municipio', 'cnpj', 'orgao', 'fornecedor', 'catmat'
    entity_id    TEXT        NOT NULL,  -- slug, cnpj, catmat code, etc.
    coverage_status TEXT     NOT NULL CHECK (coverage_status IN ('full', 'partial', 'historical_empty', 'empty')),
    last_activity_at TIMESTAMPTZ,       -- data mais recente de atividade conhecida
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (entity_type, entity_id)
);

CREATE INDEX idx_seo_coverage_manifest_status
    ON seo_coverage_manifest (entity_type, coverage_status);

COMMENT ON TABLE seo_coverage_manifest IS
    'SEO-COVERAGE-MANIFEST-001: cobertura de dados por entidade para sitemap gate — atualizado 3am BRT via cron';

-- Permissão de leitura pública (endpoint é público)
GRANT SELECT ON seo_coverage_manifest TO anon, authenticated, service_role;
GRANT INSERT, UPDATE, DELETE ON seo_coverage_manifest TO service_role;

-- Cron 3am BRT = 6h UTC: popula/atualiza a manifest table para municípios
-- O backend cron job faz a lógica principal; o pg_cron é backup.
-- Nota: a lógica completa está no job Python (seo_coverage_manifest.py).
-- O pg_cron aqui serve apenas como health-monitoring anchor (STORY-1.1).
SELECT cron.schedule(
    'seo-coverage-manifest-refresh',
    '0 6 * * *',
    $$
    -- Placeholder: marca todas as entidades sem atividade recente como stale.
    -- O job Python recalcula coverage_status com lógica completa.
    UPDATE seo_coverage_manifest
    SET updated_at = NOW()
    WHERE updated_at < NOW() - INTERVAL '25 hours';
    $$
);
