-- SEO-COVERAGE-MANIFEST-001 (#1039)
-- Coverage manifest table: tracks which slugs have actual data, so the sitemap
-- only includes URLs with real content. Rebuilt daily at 06:00 UTC by
-- backend/jobs/cron/seo_coverage_manifest.py (cron_job_health monitored).

CREATE TABLE IF NOT EXISTS seo_coverage_manifest (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    entity_type text NOT NULL,
    slug text NOT NULL,
    coverage_status text NOT NULL CHECK (coverage_status IN ('full', 'partial', 'empty', 'historical_empty')),
    bid_count integer DEFAULT 0,
    last_updated timestamptz DEFAULT now(),
    UNIQUE(entity_type, slug)
);

-- Fast lookups: (entity_type, slug) for point reads and slug list per status
CREATE INDEX IF NOT EXISTS idx_scm_entity_slug ON seo_coverage_manifest(entity_type, slug);
CREATE INDEX IF NOT EXISTS idx_scm_coverage_status ON seo_coverage_manifest(coverage_status);
CREATE INDEX IF NOT EXISTS idx_scm_entity_status ON seo_coverage_manifest(entity_type, coverage_status);

-- RLS: public read-only (coverage data is not sensitive)
ALTER TABLE seo_coverage_manifest ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Public read coverage manifest" ON seo_coverage_manifest
    FOR SELECT USING (true);

-- Insert service_role is handled by the cron job (bypasses RLS)

COMMENT ON TABLE seo_coverage_manifest IS
    'SEO-COVERAGE-MANIFEST-001: Per-slug coverage status rebuilt daily at 06:00 UTC.
     coverage_status: full (>100 bids), partial (1-100), empty (0), historical_empty (was indexed, now 0).
     Sitemap gate filters out empty slugs; historical_empty stays with priority=0.3.';
