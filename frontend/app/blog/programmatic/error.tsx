'use client';

/**
 * PSEO-004: Error boundary for /blog/programmatic/ route group.
 *
 * Catches rendering errors in the programmatic sector listing pages
 * and shows a friendly "temporarily unavailable" state.
 */

import PseoErrorFallback from '@/components/seo/PseoErrorFallback';

export default function ProgrammaticError({
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
      routeFamily="blog/programmatic"
    />
  );
}
