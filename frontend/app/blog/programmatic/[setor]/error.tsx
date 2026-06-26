'use client';

/**
 * PSEO-004: Error boundary for /blog/programmatic/[setor]/ route group.
 *
 * Catches rendering errors in the sector-level programmatic pages
 * and shows a friendly "temporarily unavailable" state.
 */

import PseoErrorFallback from '@/components/seo/PseoErrorFallback';

export default function ProgrammaticSetorError({
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
      routeFamily="blog/programmatic/[setor]"
    />
  );
}
