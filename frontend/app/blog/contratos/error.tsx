'use client';

/**
 * PSEO-004: Error boundary for /blog/contratos/ route group.
 *
 * Catches rendering errors in the contratos programmatic pages
 * and shows a friendly "temporarily unavailable" state.
 */

import PseoErrorFallback from '@/components/seo/PseoErrorFallback';

export default function ContratosError({
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
      routeFamily="blog/contratos"
    />
  );
}
