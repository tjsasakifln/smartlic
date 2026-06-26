'use client';

/**
 * PSEO-004: Shared error boundary fallback for all programmatic SEO pages.
 *
 * Renders a friendly "temporarily unavailable" state instead of a bare 500.
 * Reports to Sentry with an SEO-specific route_family tag for monitoring.
 * Injects <meta robots="noindex,follow"> so transient errors don't poison
 * the Google index (ISR preserves last-good version; this prevents crawlers
 * from caching the error state).
 *
 * Layout tokens match the blog/pSEO page family (bg-canvas, text-ink, etc.).
 */

import * as Sentry from '@sentry/nextjs';
import { useEffect, useCallback } from 'react';

export interface PseoErrorFallbackProps {
  error: Error & { digest?: string };
  reset: () => void;
  /** Sentry tag value (e.g. "blog/programmatic", "blog/contratos") */
  routeFamily: string;
}

export default function PseoErrorFallback({
  error,
  reset,
  routeFamily,
}: PseoErrorFallbackProps) {
  useEffect(() => {
    // Report to Sentry with route_family tag for SEO error monitoring
    Sentry.captureException(error, {
      tags: { route_family: routeFamily },
    });

    console.error(`[pseo-error] ${routeFamily}:`, error.message);
  }, [error, routeFamily]);

  useEffect(() => {
    // Inject meta robots noindex so transient errors don't persist in index.
    // Error boundaries are client-only, so no SSR variant is needed.
    let meta = document.querySelector<HTMLMetaElement>('meta[name="robots"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.setAttribute('name', 'robots');
      document.head.appendChild(meta);
    }
    meta.setAttribute('content', 'noindex,follow');
  }, []);

  const handleReset = useCallback(() => {
    reset();
  }, [reset]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas">
      <div className="max-w-md w-full mx-auto text-center p-8">
        <h1 className="text-2xl font-bold text-ink mb-3">
          Dados temporariamente indisponíveis
        </h1>
        <p className="text-ink-secondary mb-6">
          Nossos dados estão sendo atualizados. Tente novamente em alguns
          instantes.
        </p>
        <button
          onClick={handleReset}
          className="px-6 py-3 bg-brand-blue text-white font-medium rounded-lg hover:bg-brand-blue/90 transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    </div>
  );
}
