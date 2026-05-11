-- Rollback: SEO-COVERAGE-MANIFEST-001
SELECT cron.unschedule('seo-coverage-manifest-refresh');
DROP TABLE IF EXISTS seo_coverage_manifest;
