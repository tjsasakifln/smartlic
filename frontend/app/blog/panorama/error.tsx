'use client';

/**
 * PSEO-004: Error boundary for /blog/panorama/ route group.
 *
 * Catches rendering errors in the panorama programmatic pages
 * and shows a friendly "temporarily unavailable" state.
 */

import PseoErrorFallback from '@/components/seo/PseoErrorFallback';

export default function PanoramaError({
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
      routeFamily="blog/panorama"
    />
  );
}
