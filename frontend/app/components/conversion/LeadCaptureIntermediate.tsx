"use client";

/**
 * CONV-003-4 (#1515): LeadCaptureIntermediate
 *
 * Email capture form that appears below the PartialReportPreview cards.
 * Validates email format and POSTs to /api/lead-capture (Next.js proxy).
 *
 * States:
 *   - idle: email input + submit button
 *   - loading: disabled button + spinner
 *   - error: inline error message
 *   - success: calls onSuccess callback
 */

import { useCallback, useState, type FormEvent } from "react";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface LeadCaptureIntermediateProps {
  /** Sector ID to associate with the lead */
  sectorId: string;
  /** Source page URL for tracking */
  sourcePage: string;
  /** Called when email is successfully captured */
  onSuccess: () => void;
}

// ---------------------------------------------------------------------------
// Email validation
// ---------------------------------------------------------------------------

const EMAIL_RE = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;

function isValidEmail(email: string): boolean {
  return EMAIL_RE.test(email.trim());
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className ?? "h-5 w-5"}`}
      fill="none"
      viewBox="0 0 24 24"
      aria-hidden="true"
    >
      <circle
        className="opacity-25"
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="4"
      />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

function MailIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LeadCaptureIntermediate({
  sectorId,
  sourcePage,
  onSuccess,
}: LeadCaptureIntermediateProps) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: FormEvent) => {
      e.preventDefault();
      setError(null);

      const trimmedEmail = email.trim();

      // Client-side validation
      if (!trimmedEmail) {
        setError("Por favor, informe seu email.");
        return;
      }

      if (!isValidEmail(trimmedEmail)) {
        setError("Por favor, informe um email válido.");
        return;
      }

      // Track attempt
      if (
        typeof window !== "undefined" &&
        (window as unknown as { mixpanel?: { track: (name: string, data: unknown) => void } }).mixpanel
      ) {
        (window as unknown as { mixpanel: { track: (name: string, data: unknown) => void } }).mixpanel.track(
          "partial_preview_email_attempt",
          {
            sector_id: sectorId,
            source_page: sourcePage,
          },
        );
      }

      setLoading(true);

      try {
        const response = await fetch("/api/lead-capture", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            email: trimmedEmail,
            sector_id: sectorId,
            source_page: sourcePage,
            report_type: "partial_preview",
          }),
        });

        if (!response.ok) {
          let errorMsg = "Erro ao processar. Tente novamente.";
          try {
            const data = await response.json();
            if (data.error) errorMsg = data.error;
          } catch {
            // ignore parse errors
          }
          throw new Error(errorMsg);
        }

        // Success — call the callback
        onSuccess();
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Erro inesperado. Tente novamente.";
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    [email, sectorId, sourcePage, onSuccess],
  );

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-3"
      data-testid="lead-capture-form"
      noValidate
    >
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="flex-1 relative">
          <label htmlFor="lead-capture-email" className="sr-only">
            Email
          </label>
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <MailIcon className="w-4 h-4 text-ink-muted" />
          </div>
          <input
            id="lead-capture-email"
            type="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (error) setError(null);
            }}
            placeholder="seu@email.com"
            disabled={loading}
            className="w-full pl-10 pr-4 py-3 rounded-button border border-strong bg-surface-0 text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-blue focus:border-transparent disabled:opacity-50 disabled:cursor-not-allowed text-sm"
            data-testid="lead-capture-email-input"
            autoComplete="email"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-brand-blue text-white font-semibold rounded-button hover:bg-brand-blue-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
          data-testid="lead-capture-submit"
        >
          {loading ? (
            <>
              <SpinnerIcon />
              Enviando...
            </>
          ) : (
            "Ver relatório completo"
          )}
        </button>
      </div>

      {/* Error message */}
      {error && (
        <p
          className="text-sm text-red-600 flex items-center gap-1"
          data-testid="lead-capture-error"
          role="alert"
        >
          <svg
            className="w-4 h-4 shrink-0"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          {error}
        </p>
      )}

      <p className="text-xs text-ink-muted text-center">
        Seu email está seguro. Não enviaremos spam.
      </p>
    </form>
  );
}

export default LeadCaptureIntermediate;
