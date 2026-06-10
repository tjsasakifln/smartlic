"use client";

import { useCallback, useState } from "react";

export interface ErrorStateWithRetryProps {
  /** Main error message shown to the user */
  message: string;
  /** UX-310: Error title (opcional — se fornecido, renderiza como heading antes da mensagem) */
  errorTitle?: string;
  /** UX-310: Action suggestion (opcional — renderizado como dica abaixo da mensagem) */
  errorAction?: string;
  /** Timestamp when the error occurred (ISO string or Date) */
  timestamp?: string | Date;
  /** Callback fired when user clicks "Tentar novamente" */
  onRetry: () => void | Promise<void>;
  /** Whether a retry is currently in progress */
  retrying?: boolean;
  /** Additional CSS class for the container */
  className?: string;
  /** Compact mode for inline/card usage */
  compact?: boolean;
}

export function ErrorStateWithRetry({
  message,
  errorTitle,
  errorAction,
  timestamp,
  onRetry,
  retrying = false,
  className = "",
  compact = false,
}: ErrorStateWithRetryProps) {
  const [isRetrying, setIsRetrying] = useState(false);
  const loading = retrying || isRetrying;

  const handleRetry = useCallback(async () => {
    setIsRetrying(true);
    try {
      await onRetry();
    } finally {
      setIsRetrying(false);
    }
  }, [onRetry]);

  const formattedTime = timestamp
    ? new Date(timestamp).toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : null;

  if (compact) {
    return (
      <div
        className={`flex flex-col items-center justify-center gap-2 py-6 px-4 ${className}`}
        role="alert"
        data-testid="error-state"
      >
        <svg
          aria-hidden="true"
          className="w-6 h-6 text-[var(--error)]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
        {errorTitle && (
          <p className="text-sm font-semibold text-[var(--ink)] text-center">{errorTitle}</p>
        )}
        <p className="text-sm text-[var(--ink-secondary)] text-center">{message}</p>
        {errorAction && (
          <p className="text-xs text-[var(--ink-muted)] text-center max-w-xs">{errorAction}</p>
        )}
        <button
          onClick={handleRetry}
          disabled={loading}
          className="mt-1 px-3 py-1.5 text-xs font-medium text-[var(--brand-blue)] border border-[var(--brand-blue)] rounded-button
                     hover:bg-[var(--brand-blue-subtle)] transition-colors disabled:opacity-50 flex items-center gap-1.5"
          data-testid="error-retry-button"
        >
          {loading ? (
            <>
              <svg className="animate-spin w-3 h-3" viewBox="0 0 24 24" aria-hidden="true">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              Tentando...
            </>
          ) : (
            <>
              <svg aria-hidden="true" className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Tentar novamente
            </>
          )}
        </button>
        {formattedTime && (
          <p className="text-[10px] text-[var(--ink-muted)]">Erro em {formattedTime}</p>
        )}
      </div>
    );
  }

  return (
    <div
      className={`text-center py-12 px-4 ${className}`}
      role="alert"
      data-testid="error-state"
    >
      <div className="mx-auto mb-4 w-14 h-14 flex items-center justify-center rounded-full bg-[var(--error-subtle)]">
        <svg
          aria-hidden="true"
          className="w-7 h-7 text-[var(--error)]"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
          />
        </svg>
      </div>

      <p className="text-base font-display font-semibold text-[var(--ink)] mb-2">
        {errorTitle || message}
      </p>

      {errorTitle && (
        <p className="text-sm text-[var(--ink-secondary)] mb-1">{message}</p>
      )}
      {errorAction && (
        <p className="text-xs text-[var(--ink-muted)] mb-3 max-w-sm mx-auto">{errorAction}</p>
      )}

      {formattedTime && (
        <p className="text-xs text-[var(--ink-muted)] mb-4">Erro registrado em {formattedTime}</p>
      )}

      <button
        onClick={handleRetry}
        disabled={loading}
        className="px-5 py-2.5 bg-[var(--brand-navy)] text-white rounded-button font-medium
                   hover:bg-[var(--brand-blue)] transition-colors disabled:opacity-50
                   flex items-center gap-2 mx-auto"
        data-testid="error-retry-button"
      >
        {loading ? (
          <>
            <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" aria-hidden="true">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Tentando...
          </>
        ) : (
          <>
            <svg aria-hidden="true" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Tentar novamente
          </>
        )}
      </button>
    </div>
  );
}
