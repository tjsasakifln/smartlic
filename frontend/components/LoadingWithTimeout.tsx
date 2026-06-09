"use client";

/**
 * LoadingWithTimeout — Wrapper for loading states that might never resolve.
 *
 * UX-309: Shows children while loading normally. After 30s (configurable),
 * displays a friendly timeout message with a "Tentar novamente" button.
 * Normal flows under 5s are not affected since the timeout is well above that.
 *
 * @example
 * ```tsx
 * <LoadingWithTimeout
 *   loading={isLoading}
 *   onRetry={handleRetry}
 * >
 *   <div>Carregando...</div>
 * </LoadingWithTimeout>
 * ```
 */

import React from "react";
import { useLoadingTimeout } from "../hooks/useLoadingTimeout";

export interface LoadingWithTimeoutProps {
  /** Whether the loading state is active */
  loading: boolean;
  /** Timeout in milliseconds (default: 30000) */
  timeoutMs?: number;
  /** Callback fired when user clicks "Tentar novamente" */
  onRetry: () => void;
  /** Children rendered during normal loading (< 30s) */
  children: React.ReactNode;
  /** Custom fallback rendered after timeout (overrides default) */
  timeoutFallback?: React.ReactNode;
  /** Custom timeout message */
  timeoutMessage?: string;
  /** Additional CSS class for the timeout state container */
  className?: string;
}

export function LoadingWithTimeout({
  loading,
  timeoutMs = 30000,
  onRetry,
  children,
  timeoutFallback,
  timeoutMessage,
  className = "",
}: LoadingWithTimeoutProps) {
  const { timedOut, reset, timeLeft } = useLoadingTimeout({
    timeoutMs,
    enabled: loading,
  });

  const handleRetry = () => {
    reset();
    onRetry();
  };

  // Not loading — render children directly
  if (!loading) {
    return <>{children}</>;
  }

  // Loading but within normal timeframe — render children as-is
  if (!timedOut) {
    return <>{children}</>;
  }

  // Timed out — show fallback
  if (timeoutFallback) {
    return <>{timeoutFallback}</>;
  }

  // Default timeout fallback UI
  return (
    <div
      className={`flex flex-col items-center justify-center py-12 px-4 text-center ${className}`}
      role="alert"
      data-testid="loading-timeout"
    >
      <div className="mx-auto mb-4 w-14 h-14 flex items-center justify-center rounded-full bg-amber-50 dark:bg-amber-900/20">
        <svg
          className="w-7 h-7 text-amber-600 dark:text-amber-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      </div>
      <p className="text-base font-display font-semibold text-ink mb-2">
        {timeoutMessage || "Isto está demorando mais que o esperado"}
      </p>
      <p className="text-sm text-ink-secondary mb-6 max-w-md">
        A requisição está demorando mais do que o normal. Tente novamente ou
        volte mais tarde.
      </p>
      <button
        onClick={handleRetry}
        className="px-5 py-2.5 bg-brand-navy text-white rounded-button font-medium hover:bg-brand-blue transition-colors flex items-center gap-2 mx-auto"
        data-testid="loading-timeout-retry"
        type="button"
      >
        <svg
          className="w-4 h-4"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
        Tentar novamente
      </button>
    </div>
  );
}
