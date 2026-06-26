'use client';

/**
 * PSEO-004: Error boundary for /blog/licitacoes/ route group.
 *
 * Catches rendering errors in the licitacoes programmatic pages
 * and shows a friendly "temporarily unavailable" state.
 */

import PseoErrorFallback from '@/components/seo/PseoErrorFallback';

export default function LicitacoesError({
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
      routeFamily="blog/licitacoes"
    />
  );
}
