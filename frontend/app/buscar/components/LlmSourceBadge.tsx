interface LlmSourceBadgeProps {
  llmSource: "ai" | "fallback" | "processing" | null | undefined;
}

/**
 * CRIT-005 AC16: Discrete badge showing LLM summary provenance.
 * - "ai" → blue badge "Análise automática"
 * - "fallback" → gray badge "Análise automática"
 * - "processing" → animated badge "Análise automática sendo preparada..."
 */
export function LlmSourceBadge({ llmSource }: LlmSourceBadgeProps) {
  if (!llmSource) return null;

  if (llmSource === "processing") {
    return (
      <span
        className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300 animate-pulse"
        title="A análise está sendo gerada automaticamente"
      >
        <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" aria-hidden="true">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
        Análise automática sendo preparada...
      </span>
    );
  }

  if (llmSource === "ai") {
    return (
      <span
        className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300"
        title="Analisado automaticamente com base em padrões do setor"
      >
        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        Análise automática
      </span>
    );
  }

  // fallback
  return (
    <span
      className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"
      title="Este resumo foi gerado automaticamente"
    >
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
      Análise automática
    </span>
  );
}
