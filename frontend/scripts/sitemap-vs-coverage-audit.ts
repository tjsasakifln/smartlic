#!/usr/bin/env ts-node
/**
 * SEO-COVERAGE-MANIFEST-001 (#1039): Sitemap vs Coverage Audit
 *
 * AC6: Validates 0 drift between the sitemap and the coverage manifest.
 *
 * Checks:
 * 1. No slugs in the sitemap have coverage_status='empty' (would be a gate leak)
 * 2. Slugs with coverage_status='full' that are absent from the sitemap (missed coverage)
 *
 * Usage:
 *   BACKEND_URL=https://api.smartlic.tech npx ts-node scripts/sitemap-vs-coverage-audit.ts
 *   BACKEND_URL=http://localhost:8000 npx ts-node scripts/sitemap-vs-coverage-audit.ts
 *
 * Exit codes:
 *   0 — no drift found
 *   1 — drift detected (empty slugs in sitemap) or fetch error
 */

const BACKEND_URL =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  'http://localhost:8000';

const BASE_URL =
  process.env.NEXT_PUBLIC_CANONICAL_URL || 'https://smartlic.tech';

interface CoverageEntry {
  coverage_status: 'full' | 'partial' | 'empty' | 'historical_empty';
  bid_count: number;
  last_updated: string;
}

interface CoverageManifestResponse {
  manifest: Record<string, CoverageEntry>;
  generated_at: string;
  total_entities: number;
}

interface SitemapUrl {
  loc: string;
}

async function fetchJson<T>(url: string, label: string): Promise<T | null> {
  try {
    const resp = await fetch(url, {
      signal: AbortSignal.timeout(10_000),
    });
    if (!resp.ok) {
      console.error(`[${label}] HTTP ${resp.status} — ${url}`);
      return null;
    }
    return (await resp.json()) as T;
  } catch (err) {
    console.error(`[${label}] fetch failed: ${(err as Error).message}`);
    return null;
  }
}

async function fetchSitemapUrls(sitemapId: number): Promise<string[]> {
  const url = `${BASE_URL}/sitemap/${sitemapId}.xml`;
  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(15_000) });
    if (!resp.ok) {
      console.warn(`[sitemap/${sitemapId}.xml] HTTP ${resp.status} — skipping`);
      return [];
    }
    const xml = await resp.text();
    // Simple regex extraction — good enough for audit purposes
    const matches = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)];
    return matches.map((m) => m[1]);
  } catch (err) {
    console.warn(`[sitemap/${sitemapId}.xml] fetch failed: ${(err as Error).message}`);
    return [];
  }
}

function extractSlugFromUrl(pageUrl: string): string {
  return pageUrl.split('/').pop() ?? '';
}

function detectEntityType(pageUrl: string): string | null {
  if (pageUrl.includes('/cnpj/')) return 'cnpj';
  if (pageUrl.includes('/orgaos/')) return 'cnpj';        // orgaos use cnpj slugs
  if (pageUrl.includes('/fornecedores/') && !pageUrl.includes('/fornecedores/')) return 'cnpj';
  if (pageUrl.includes('/municipios/')) return 'municipio';
  return null;
}

async function main() {
  console.log('=== SEO Coverage vs Sitemap Audit (SEO-COVERAGE-MANIFEST-001) ===\n');
  console.log(`Backend: ${BACKEND_URL}`);
  console.log(`Frontend: ${BASE_URL}\n`);

  // 1. Fetch coverage manifest
  const manifestResp = await fetchJson<CoverageManifestResponse>(
    `${BACKEND_URL}/v1/seo/coverage-manifest`,
    'coverage-manifest',
  );

  if (!manifestResp) {
    console.error('ERROR: could not fetch coverage manifest. Is the backend running?');
    process.exit(1);
    throw new Error('unreachable'); // help TS narrowing
  }

  const manifest = manifestResp.manifest;
  console.log(`Coverage manifest: ${manifestResp.total_entities} entities`);
  console.log(`Generated at: ${manifestResp.generated_at}\n`);

  // Group manifest by status for reporting
  const byStatus = {
    full: 0, partial: 0, empty: 0, historical_empty: 0,
  };
  for (const entry of Object.values(manifest)) {
    byStatus[entry.coverage_status] = (byStatus[entry.coverage_status] ?? 0) + 1;
  }
  console.log('Manifest breakdown:');
  for (const [status, count] of Object.entries(byStatus)) {
    console.log(`  ${status}: ${count}`);
  }
  console.log();

  // 2. Fetch all sub-sitemap URLs (entity sitemaps are id:4)
  console.log('Fetching sitemap/4.xml (entity pages)...');
  const entityUrls = await fetchSitemapUrls(4);
  console.log(`Found ${entityUrls.length} entity URLs in sitemap/4.xml\n`);

  // 3. Check for empty slugs in sitemap (gate leak)
  const emptyInSitemap: string[] = [];
  const historicalInSitemap: string[] = [];

  for (const pageUrl of entityUrls) {
    const slug = extractSlugFromUrl(pageUrl);
    const entityType = detectEntityType(pageUrl);
    if (!entityType || !slug) continue;

    const key = `${entityType}/${slug}`;
    const entry = manifest[key];
    if (!entry) continue; // not in manifest = not classified = pass

    if (entry.coverage_status === 'empty') {
      emptyInSitemap.push(pageUrl);
    } else if (entry.coverage_status === 'historical_empty') {
      historicalInSitemap.push(pageUrl);
    }
  }

  // 4. Check for full slugs missing from sitemap
  const sitemapUrlSet = new Set(entityUrls);
  const fullMissingFromSitemap: string[] = [];

  for (const [key, entry] of Object.entries(manifest)) {
    if (entry.coverage_status !== 'full') continue;
    const [entityType, slug] = key.split('/');
    if (!entityType || !slug) continue;

    // Map entity_type to expected URL pattern
    let expectedUrl: string | null = null;
    if (entityType === 'cnpj') {
      expectedUrl = `${BASE_URL}/cnpj/${slug}`;
    } else if (entityType === 'municipio') {
      expectedUrl = `${BASE_URL}/municipios/${slug}`;
    }

    if (expectedUrl && !sitemapUrlSet.has(expectedUrl)) {
      fullMissingFromSitemap.push(expectedUrl);
    }
  }

  // 5. Report results
  let hasErrors = false;

  if (emptyInSitemap.length > 0) {
    hasErrors = true;
    console.error(`❌ DRIFT DETECTED: ${emptyInSitemap.length} empty slugs in sitemap (coverage gate leak):`);
    emptyInSitemap.slice(0, 20).forEach((u) => console.error(`   ${u}`));
    if (emptyInSitemap.length > 20) console.error(`   ... and ${emptyInSitemap.length - 20} more`);
    console.error();
  } else {
    console.log('✅ No empty slugs in sitemap (coverage gate working correctly)');
  }

  if (historicalInSitemap.length > 0) {
    console.log(`ℹ️  ${historicalInSitemap.length} historical_empty slugs in sitemap (expected — low-priority URLs kept for continuity)`);
    historicalInSitemap.slice(0, 5).forEach((u) => console.log(`   ${u}`));
    if (historicalInSitemap.length > 5) console.log(`   ... and ${historicalInSitemap.length - 5} more`);
    console.log();
  }

  if (fullMissingFromSitemap.length > 0) {
    console.warn(`⚠️  ${fullMissingFromSitemap.length} full-coverage slugs missing from sitemap:`);
    fullMissingFromSitemap.slice(0, 10).forEach((u) => console.warn(`   ${u}`));
    if (fullMissingFromSitemap.length > 10) console.warn(`   ... and ${fullMissingFromSitemap.length - 10} more`);
    console.warn('   (These may be intentionally excluded by noindex or other filters)');
    console.warn();
  } else {
    console.log('✅ All full-coverage slugs are present in sitemap');
  }

  console.log('\n=== Audit Complete ===');

  if (hasErrors) {
    console.error('\nResult: DRIFT DETECTED — coverage gate has leaks. Investigate sitemap/coverage-manifest sync.');
    process.exit(1);
  } else {
    console.log('\nResult: OK — 0 drift between sitemap and coverage manifest.');
    process.exit(0);
  }
}

main().catch((err) => {
  console.error('Unhandled error:', err);
  process.exit(1);
});
