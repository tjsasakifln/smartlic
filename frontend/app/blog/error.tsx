'use client';

/**
 * PSEO-004: Catch-all error boundary for /blog/* route group.
 *
 * Catches rendering errors in blog pages that don't have a more specific
 * error boundary (e.g. author pages, blog listing, weekly, rss, etc.).
 *
 * More specific error boundaries in sub-routes (programmatic, contratos,
 * licitacoes, panorama) will catch errors before this one fires.
 *
 * Does NOT cover errors in generateMetadata (Next.js limitation) — those
 * are handled by safeMetadataFetch in lib/seo-metadata.ts.
 */

import PseoErrorFallback from '@/components/seo/PseoErrorFallback';

export default function BlogError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <PseoErrorFallback
      error={error}
      reset={reset}
      routeFamily="blog"
    />
  );
}
