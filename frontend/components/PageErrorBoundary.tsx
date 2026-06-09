"use client";

import React, { Component, ErrorInfo } from "react";
import { getStructuredError } from "@/lib/error-messages";

interface PageErrorBoundaryProps {
  children: React.ReactNode;
  /** Contextual page name shown in error message (e.g. "dashboard", "pipeline") */
  pageName: string;
}

interface PageErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * DEBT-112: Error boundary for authenticated pages that preserves NavigationShell.
 * Catches render errors and displays contextual recovery UI without losing
 * sidebar/bottom nav (NavigationShell lives in layout.tsx, above this boundary).
 *
 * Does NOT clear localStorage or SWR cache on error (AC8).
 */
export class PageErrorBoundary extends Component<PageErrorBoundaryProps, PageErrorBoundaryState> {
  constructor(props: PageErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): PageErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(
      `[PageErrorBoundary:${this.props.pageName}] Component crash:`,
      error,
      errorInfo
    );
    try {
      import("@sentry/nextjs")
        .then((Sentry) => {
          Sentry.captureException(error, {
            extra: {
              componentStack: errorInfo.componentStack,
              pageName: this.props.pageName,
            },
          });
        })
        .catch(() => {});
    } catch {}
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          aria-live="assertive"
          className="min-h-[60vh] flex items-center justify-center px-4"
        >
          <div className="max-w-md w-full text-center">
            <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-full bg-amber-100 dark:bg-amber-900/40">
              <svg
                className="h-8 w-8 text-amber-600 dark:text-amber-400"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth="1.5"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
                />
              </svg>
            </div>

            <h2 className="text-xl font-semibold text-[var(--ink)] mb-2">
              Erro ao carregar o {this.props.pageName}
            </h2>
            <p className="text-sm text-[var(--ink-secondary)] mb-1">
              {this.state.error
                ? getStructuredError(this.state.error).description
                : "Ocorreu um erro inesperado. Nossa equipe já foi notificada."}
            </p>
            <p className="text-xs text-[var(--ink-muted)] mb-6">
              {this.state.error
                ? getStructuredError(this.state.error).action
                : "Tente novamente. Se o problema persistir, entre em contato com o suporte."}
            </p>

            <button
              onClick={this.handleRetry}
              className="rounded-button bg-[var(--brand-navy)] px-5 py-2.5 text-sm font-semibold text-white hover:bg-[var(--brand-blue)] transition-colors"
            >
              Tentar novamente
            </button>

            <details className="mt-6 text-left">
              <summary className="cursor-pointer text-xs text-[var(--ink-muted)] hover:underline">
                Detalhes técnicos
              </summary>
              <pre className="mt-2 rounded-lg bg-[var(--surface-1)] p-3 text-xs text-[var(--ink-secondary)] overflow-auto max-h-32">
                {this.state.error?.message || "Erro desconhecido"}
              </pre>
            </details>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
