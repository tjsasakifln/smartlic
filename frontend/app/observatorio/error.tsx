'use client';

/** SEO error boundary — /observatorio/* */

import { useEffect } from 'react';

export default function ObservatorioError({
  error,
  reset,
}: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error('[observatorio/error]:', error.message); }, [error]);
  return (
    <div className="min-h-screen flex items-center justify-center bg-canvas">
      <div className="max-w-md w-full mx-auto text-center p-8">
        <h1 className="text-2xl font-bold text-ink mb-3">Página temporariamente indisponível</h1>
        <p className="text-ink-secondary mb-6">Nossos dados estão sendo atualizados. Tente novamente em alguns instantes.</p>
        <button onClick={reset} className="px-6 py-3 bg-brand-blue text-white font-medium rounded-lg hover:bg-brand-blue/90 transition-colors">Tentar novamente</button>
      </div>
    </div>
  );
}
