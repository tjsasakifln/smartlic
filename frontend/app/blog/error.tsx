'use client';

/**
 * SEO programmatic error boundary — /blog/*
 *
 * Catches rendering errors in ISR page components and shows a friendly
 * "temporarily unavailable" state instead of a bare 500.
 *
 * Does NOT cover errors in generateMetadata (Next.js limitation) — those
 * are handled by safeMetadataFetch in lib/seo-metadata.ts.
 */

import { useEffect } from 'react';

export default function BlogError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('[blog/error] page render error:', error.message);
  }, [error]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas">
      <div className="max-w-md w-full mx-auto text-center p-8">
        <h1 className="text-2xl font-bold text-ink mb-3">
          Página temporariamente indisponível
        </h1>
        <p className="text-ink-secondary mb-6">
          Nossos dados estão sendo atualizados. Tente novamente em alguns instantes.
        </p>
        <button
          onClick={reset}
          className="px-6 py-3 bg-brand-blue text-white font-medium rounded-lg hover:bg-brand-blue/90 transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    </div>
  );
}
