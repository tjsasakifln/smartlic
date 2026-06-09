"use client";

import Link from "next/link";
import type { SearchProgressEvent, SourceStatus, PartialProgress, FilterSummary, UfStatus } from "../../../../hooks/useSearchSSE";
import { EnhancedLoadingProgress } from "../EnhancedLoadingProgress";
import { LoadingResultsSkeleton } from "../../../components/LoadingResultsSkeleton";
import { PartialResultsPrompt } from "../PartialResultsPrompt";
import SourceStatusGrid from "../SourceStatusGrid";

interface ResultsLoadingSectionProps {
  loading: boolean;
  loadingStep: number;
  estimatedTime: number;
  stateCount: number;
  statesProcessed: number;
  onCancel: () => void;
  onSearch: () => void;
  sseEvent: SearchProgressEvent | null;
  useRealProgress: boolean;
  sseAvailable: boolean;
  sseDisconnected?: boolean;
  isReconnecting?: boolean;
  isDegraded?: boolean;
  onStageChange: (stage: number) => void;
  ufAllComplete?: boolean;
  skeletonTimeoutReached?: boolean;
  sourceStatuses?: Map<string, SourceStatus>;
  partialProgress?: PartialProgress | null;
  filterSummary?: FilterSummary | null;
  searchElapsedSeconds: number;
  ufTotalFound: number;
  succeededUfCount: number;
  pendingUfCount: number;
  partialDismissed?: boolean;
  onViewPartial?: () => void;
  onDismissPartial?: () => void;
}

/**
 * TD-007: Loading state section extracted from SearchResults orchestrator.
 * Renders progress indicators, skeleton, source status, filter counters, and partial prompts.
 */
export function ResultsLoadingSection({
  loading, loadingStep, estimatedTime, stateCount, statesProcessed,
  onCancel, onSearch, sseEvent, useRealProgress, sseAvailable, sseDisconnected,
  isReconnecting, isDegraded, onStageChange, ufAllComplete, skeletonTimeoutReached,
  sourceStatuses, partialProgress, filterSummary,
  searchElapsedSeconds, ufTotalFound, succeededUfCount, pendingUfCount,
  partialDismissed, onViewPartial, onDismissPartial,
}: ResultsLoadingSectionProps) {
  if (!loading) return null;

  return (
    <div aria-live="polite">
      <div className="sticky top-[68px] z-30 bg-[var(--canvas)] pb-2">
        <EnhancedLoadingProgress
          currentStep={loadingStep} estimatedTime={estimatedTime}
          stateCount={stateCount} statesProcessed={statesProcessed}
          onCancel={onCancel} sseEvent={sseEvent}
          useRealProgress={useRealProgress && sseAvailable}
          sseDisconnected={sseDisconnected} isReconnecting={isReconnecting}
          onStageChange={onStageChange} ufAllComplete={ufAllComplete}
          isDegraded={isDegraded}
          degradedMessage={sseEvent?.stage === 'degraded' ? sseEvent.message : undefined}
          ufTotalFound={ufTotalFound}
          onViewPartial={onViewPartial}
          onRetry={() => { onCancel?.(); onSearch(); }}
        />
      </div>
      <LoadingResultsSkeleton count={1} />

      {/* SAB-005 AC1-AC3: Timeout banner */}
      {skeletonTimeoutReached && (
        <div className="mt-4 p-4 rounded-xl bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 animate-fade-in-up" role="alert" data-testid="skeleton-timeout-banner">
          <div className="flex items-start gap-3">
            <svg className="w-5 h-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div className="flex-1">
              <p className="text-sm font-medium text-amber-800 dark:text-amber-200">A análise está demorando mais que o esperado</p>
              <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">O servidor pode estar processando um volume alto de dados.</p>
              <div className="flex flex-col sm:flex-row items-start gap-2 mt-3">
                <button onClick={() => { onCancel(); onSearch(); }} className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 transition-colors" type="button" data-testid="skeleton-timeout-retry">Tentar novamente</button>
                <Link href="/historico" className="px-4 py-2 text-sm font-medium text-amber-700 dark:text-amber-300 hover:underline" data-testid="skeleton-timeout-historico">Ver análises anteriores</Link>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Source status indicators */}
      {sourceStatuses && sourceStatuses.size > 0 && <SourceStatusGrid sourceStatuses={sourceStatuses} className="mt-3" />}

      {/* Unified counter banner */}
      {(filterSummary || (partialProgress && partialProgress.totalSoFar > 0)) && (
        <div className="mt-3 p-3 rounded-lg bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800 animate-fade-in-up">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0 animate-pulse" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
              <span className="text-sm font-medium text-blue-800 dark:text-blue-200" data-testid="unified-counter-banner">
                {filterSummary
                  ? `${filterSummary.totalFiltered} ${filterSummary.totalFiltered === 1 ? "relevante" : "relevantes"} de ${filterSummary.totalRaw.toLocaleString("pt-BR")} analisadas`
                  : `Analisando ${partialProgress!.totalSoFar.toLocaleString("pt-BR")} licitações encontradas — aplicando filtros do setor...`}
              </span>
            </div>
            <span className="text-xs text-blue-600 dark:text-blue-400">{filterSummary ? "Filtragem concluída" : "Análise em andamento"}</span>
          </div>
        </div>
      )}

      {/* Zero filtered suggestion */}
      {filterSummary && filterSummary.totalFiltered === 0 && filterSummary.totalRaw > 0 && (
        <div className="mt-3 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800 animate-fade-in-up" data-testid="zero-filtered-suggestion">
          <p className="text-sm text-amber-800 dark:text-amber-200">Nenhuma oportunidade relevante entre {filterSummary.totalRaw.toLocaleString("pt-BR")} licitações. Tente ampliar o período ou selecionar mais estados.</p>
        </div>
      )}

      {/* Partial results prompt */}
      {searchElapsedSeconds >= 15 && ufTotalFound > 0 && !partialDismissed && onViewPartial && onDismissPartial && (
        <PartialResultsPrompt
          totalFound={ufTotalFound} succeededCount={succeededUfCount}
          pendingCount={pendingUfCount} elapsedSeconds={searchElapsedSeconds}
          onViewPartial={onViewPartial} onWaitComplete={onDismissPartial}
          dismissed={!!partialDismissed}
        />
      )}
    </div>
  );
}
