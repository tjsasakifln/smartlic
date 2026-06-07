// CONV-010-3: Homepage refatorada como terminal de inteligencia (#1510)
// Route: / (root)
// Substitui a landing page institucional estatica por um terminal de busca + cartoes de intent.
import { Suspense } from 'react';
import { HomeFaqStructuredData } from './components/HomeFaqStructuredData';
import IntelHomeClient from './components/conversion/IntelHomeClient';

/**
 * Skeleton de carregamento para o IntelHomeClient.
 * Exibe enquanto o componente cliente hidrata (Suspense boundary).
 */
function HomePageSkeleton() {
  return (
    <div className="min-h-screen bg-canvas" data-testid="homepage-skeleton">
      {/* Search skeleton */}
      <div className="flex flex-col items-center justify-center px-4 pb-16 pt-24 md:pb-24 md:pt-32">
        <div className="mb-6 h-12 w-96 animate-pulse rounded-lg bg-surface-2" />
        <div className="mb-10 h-6 w-72 animate-pulse rounded bg-surface-2" />
        <div className="flex h-12 w-full max-w-2xl animate-pulse rounded-xl bg-surface-2" />
      </div>
      {/* Cards skeleton */}
      <div className="mx-auto max-w-landing px-4 pb-24">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 md:gap-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl bg-surface-2" />
          ))}
        </div>
      </div>
    </div>
  );
}

export default function HomePage() {
  return (
    <>
      <HomeFaqStructuredData />
      <Suspense fallback={<HomePageSkeleton />}>
        <IntelHomeClient />
      </Suspense>
    </>
  );
}
