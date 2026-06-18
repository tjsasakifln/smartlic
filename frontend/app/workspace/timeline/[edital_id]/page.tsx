"use client";

import { useParams } from "next/navigation";
import { TimelineFeed } from "../../../../components/workspace/timeline/TimelineFeed";
import { PageHeader } from "../../../../components/PageHeader";
import { ErrorBoundary } from "../../../../components/ErrorBoundary";

export default function TimelinePage() {
  const params = useParams();
  const editalId = params.edital_id as string;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-display font-semibold text-[var(--ink)]">
          Timeline do Edital
        </h1>
        <p className="mt-1 text-sm text-[var(--ink-secondary)]">
          Acompanhe eventos, notas e lembretes deste edital em ordem cronologica.
        </p>
      </div>

      <ErrorBoundary>
        <TimelineFeed editalId={editalId} />
      </ErrorBoundary>
    </div>
  );
}
