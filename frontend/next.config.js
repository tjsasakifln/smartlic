const path = require("path");
const { withSentryConfig } = require("@sentry/nextjs");
const { buildLegacyLicitacoesRedirects } = require("./lib/legacy-licitacoes-redirects");

// STORY-5.10 (TD-FE-012): Opt-in bundle analyzer. Run via `npm run analyze`,
// which sets ANALYZE=true. Reports are written under .next/analyze/*.html.
const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
  openAnalyzer: false,
});

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  trailingSlash: false,
  output: 'standalone',

  // BUILD-FIX-2026-06-01: Aumentar staticPageGenerationTimeout para 300s.
  // Default 60s insuficiente para ISR com 200+ páginas × fetch backend.
  // Sem isso, cascade timeout → 3 retries → build falha.
  staticPageGenerationTimeout: 300,
  // Fix standalone output when repo has multiple lockfiles (root + frontend)
  // Without this, Next.js infers the wrong workspace root and server.js
  // ends up in a nested path instead of .next/standalone/server.js
  outputFileTracingRoot: path.join(__dirname, './'),
  // CRITICAL: Generate unique build ID to force cache invalidation on deploy
  // This prevents "Failed to find Server Action" errors from stale client bundles
  generateBuildId: async () => {
    // Use timestamp + random for true uniqueness (not git commit)
    return `build-${Date.now()}-${Math.random().toString(36).substring(7)}`;
  },
  images: {
    // Issue #994: Pin modern formats (AVIF first, WebP fallback) for next/image
    // optimization on blog hero, author avatars, and any future imagery. Next.js
    // 16 default already includes both, but pinning makes intent explicit and
    // survives upstream default changes.
    formats: ['image/avif', 'image/webp'],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'static.wixstatic.com',
        pathname: '/media/**',
      },
    ],
  },

  // STORY-5.10 (TD-FE-012): Tree-shake heavy UI/interaction packages.
  // Next's optimizePackageImports rewrites `import { X } from 'pkg'` to
  // `import X from 'pkg/dist/X'`, eliminating transitively pulled symbols.
  // Validated targets: all framer-motion callsites use named imports
  // (motion, AnimatePresence, useInView); all @dnd-kit callsites use
  // named imports (useSortable, useDroppable, SortableContext, CSS, ...).
  experimental: {
    optimizePackageImports: [
      'framer-motion',
      '@dnd-kit/core',
      '@dnd-kit/sortable',
      '@dnd-kit/utilities',
    ],
  },
  // STORY-311 AC5: Security headers unified in middleware.ts (removed duplication).
  // Middleware covers all non-static routes. Static assets (_next/static, images)
  // don't need CSP/X-Frame-Options. HSTS is enforced at Railway edge proxy level.

  // SEO: Redirect acentuado → slug canônico (ISSUE-SEO-004)
  // SEO: Consolidar pricing pages — /pricing → /planos (ISSUE-SEO-005)
  // Fix #870: Redirecionar /founding → /fundadores (301 permanente)
  async redirects() {
    return [
      ...buildLegacyLicitacoesRedirects(),
      {
        source: '/founding/obrigado',
        destination: '/fundadores/obrigado',
        permanent: true,
      },
      {
        source: '/founding',
        destination: '/fundadores',
        permanent: true,
      },
      {
        source: '/founding/:path*',
        destination: '/fundadores/:path*',
        permanent: true,
      },
      {
        source: '/gloss%C3%A1rio',
        destination: '/glossario',
        permanent: true,
      },
      {
        source: '/gloss\u00E1rio',
        destination: '/glossario',
        permanent: true,
      },
      {
        source: '/gloss%C3%A1rio/:path*',
        destination: '/glossario/:path*',
        permanent: true,
      },
      {
        source: '/gloss\u00E1rio/:path*',
        destination: '/glossario/:path*',
        permanent: true,
      },
      {
        source: '/pricing',
        destination: '/planos',
        permanent: true,
      },
    ];
  },

  // Issue #1806: Rewrite /api/openapi.json to backend FastAPI OpenAPI schema.
  // Next.js catches /api/* paths and looks for route handlers, but there is
  // no app/api/openapi.json/ route — the backend serves it at /openapi.json.
  async rewrites() {
    return [
      {
        source: '/api/openapi.json',
        destination: `${process.env.BACKEND_URL || 'http://localhost:8000'}/openapi.json`,
      },
    ];
  },

  // Issue #1868 — CDN-ready Cache-Control headers by content type.
  // AC2: Assets estaticos com cache longo (1 ano + immutable para fingerprint).
  // Static assets (JS/CSS bundles) servidos via Cloudflare CDN.
  // max-age=31536000 (1 ano) + immutable permite CDN caching geografico
  // sem revalidacao. Build ID unico (generateBuildId acima) garante que
  // novas versoes tenham URLs diferentes — nunca servem stale.
  // AC4: Security headers (CSP, HSTS, X-Frame-Options) NAO sao afetados aqui
  // — estes headers sao aplicados pelo middleware.ts para todas as rotas HTML
  // e API routes. Assets estaticos nao precisam de CSP/X-Frame-Options.
  async headers() {
    return [
      // AC2: 1 ano + immutable para JS/CSS bundles com fingerprint.
      // Build ID unico (generateBuildId) garante URL unica por deploy →
      // cache nunca precisa ser purgado manualmente para _next/static.
      {
        source: '/_next/static/:path*',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' },
          // AC5: Via header para identificar origem CDN nas metricas
          { key: 'X-CDN-Strategy', value: 'immutable-1y' },
        ],
      },
      {
        source: '/images/:path*',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=604800, stale-while-revalidate=86400' },
          { key: 'X-CDN-Strategy', value: 'images-7d' },
        ],
      },
      {
        source: '/fonts/:path*',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=31536000, immutable' },
          { key: 'X-CDN-Strategy', value: 'fonts-1y' },
        ],
      },
      // AC2: Sitemap XML servidos via CDN com cache de 1h + stale-while-revalidate.
      // s-maxage=86400 permite CDN edge cache por 24h.
      {
        source: '/sitemap/:path*',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=3600, s-maxage=86400, stale-while-revalidate=86400, stale-if-error=86400' },
          { key: 'X-CDN-Strategy', value: 'sitemap-1h' },
        ],
      },
      // AC2: public/ assets (favicon, manifest, txt, xml, json, pdf, svg)
      // — cache de 1h com stale-while-revalidate. URLs fixas (sem fingerprint)
      // precisam de stale-while-revalidate para evitar revalidacao constante.
      // Regex exclui paths ja cobertos acima.
      {
        source: '/:path((?!_next/static|images|fonts|sitemap).*)\\.(txt|ico|xml|json|pdf|svg)$',
        headers: [
          { key: 'Cache-Control', value: 'public, max-age=3600, stale-while-revalidate=86400' },
          { key: 'X-CDN-Strategy', value: 'public-assets-1h' },
        ],
      },
    ];
  },
}

// STORY-211: Wrap with Sentry for error tracking and source map upload (AC8).
// STORY-5.10 (TD-FE-012): Wrap with Bundle Analyzer (opt-in via ANALYZE=true).
module.exports = withSentryConfig(withBundleAnalyzer(nextConfig), {
  org: process.env.SENTRY_ORG,
  project: process.env.SENTRY_PROJECT,
  authToken: process.env.SENTRY_AUTH_TOKEN,

  // Only print logs for uploading source maps in CI
  silent: !process.env.CI,

  // Upload larger set of source maps for prettier stack traces
  widenClientFileUpload: true,

  // Route browser requests to Sentry through Next.js rewrite to circumvent ad-blockers
  tunnelRoute: "/monitoring",

  // Hides source maps from generated client bundles
  hideSourceMaps: true,

  // Tree-shake Sentry debug logger statements to reduce bundle size
  bundleSizeOptimizations: {
    excludeDebugStatements: true,
  },
});
