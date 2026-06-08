"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { PartialReportPreview } from "./PartialReportPreview";
import type { PartialReportPreviewProps } from "./PartialReportPreview";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ContextualCaptureProps {
  /** 3 free preview items. */
  previewData: { label: string; value: string }[];
  /** 5 blurred/premium items. */
  blurredData: { label: string }[];
  /** Product SKU for checkout. */
  productSku: string;
  /** Context forwarded to checkout. */
  contextInfo: { entity_type: string; entity_id: string };
  /**
   * Scroll threshold (0–1). The capture appears when the user has scrolled
   * this fraction of the page. Defaults to 0.6 (60%).
   */
  scrollThreshold?: number;
  /**
   * When true, skips the email gate and shows PartialReportPreview directly
   * once the scroll threshold is reached. For authenticated users.
   */
  isAuthenticated?: boolean;
}

// ---------------------------------------------------------------------------
// Tracking helper
// ---------------------------------------------------------------------------

function trackEvent(
  name: string,
  extra?: Record<string, unknown>,
): void {
  if (typeof window === "undefined") return;
  const mp = (
    window as unknown as {
      mixpanel?: {
        track: (e: string, p?: Record<string, unknown>) => void;
      };
    }
  ).mixpanel;
  if (!mp) return;
  try {
    mp.track(name, extra);
  } catch {
    /* best-effort */
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ContextualCapture({
  previewData,
  blurredData,
  productSku,
  contextInfo,
  scrollThreshold = 0.6,
  isAuthenticated = false,
}: ContextualCaptureProps) {
  const [visible, setVisible] = useState(false);
  const [emailSubmitted, setEmailSubmitted] = useState(false);
  const [capturedEmail, setCapturedEmail] = useState("");
  const hasTrackedImpression = useRef(false);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  // Track visibility
  useEffect(() => {
    if (visible && !hasTrackedImpression.current) {
      hasTrackedImpression.current = true;
      trackEvent("contextual_capture_impression", contextInfo);
    }
  }, [visible, contextInfo]);

  // --- Strategy A: IntersectionObserver (modern, passive) ---
  // The component renders a hidden sentinel. When ~60% of the page has
  // scrolled past the sentinel we consider the threshold reached.
  // Fallback: scroll listener.

  useEffect(() => {
    // Try IntersectionObserver first
    if (typeof IntersectionObserver !== "undefined" && sentinelRef.current) {
      observerRef.current = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting && !visible) {
              setVisible(true);
            }
          }
        },
        { threshold: 0 },
      );
      observerRef.current.observe(sentinelRef.current);

      return () => {
        observerRef.current?.disconnect();
      };
    }

    // Fallback: scroll listener
    const handleScroll = () => {
      if (visible) return;
      const scrollTop = window.scrollY;
      const docHeight =
        document.documentElement.scrollHeight - window.innerHeight;
      const progress = docHeight > 0 ? scrollTop / docHeight : 0;
      if (progress >= scrollThreshold) {
        setVisible(true);
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scrollThreshold]);

  const handleEmailSubmit = useCallback((email: string) => {
    setCapturedEmail(email);
    setEmailSubmitted(true);
    trackEvent("contextual_capture_submit", {
      ...contextInfo,
      email_domain: email.split("@")[1] ?? "",
    });
  }, [contextInfo]);

  if (!visible) {
    return (
      <div
        ref={sentinelRef}
        className="not-prose h-px w-full"
        aria-hidden="true"
        data-testid="contextual-capture-sentinel"
      />
    );
  }

  // After scroll threshold reached: show PartialReportPreview directly
  // for authenticated users, or after email submit for anonymous users.
  if (isAuthenticated) {
    return (
      <PartialReportPreview
        previewData={previewData}
        blurredData={blurredData}
        productSku={productSku}
        contextInfo={contextInfo}
      />
    );
  }

  // After email submit, show the PartialReportPreview with pre-captured email
  if (emailSubmitted) {
    return (
      <PartialReportPreview
        previewData={previewData}
        blurredData={blurredData}
        productSku={productSku}
        contextInfo={contextInfo}
        preCapturedEmail={capturedEmail}
      />
    );
  }

  // Email capture form
  return (
    <section
      className="not-prose my-8 sm:my-10"
      data-testid="contextual-capture"
    >
      <div className="rounded-xl border border-brand-blue/20 bg-gradient-to-br from-brand-blue-subtle/60 to-surface-0 p-5 sm:p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row items-center gap-4">
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-ink">
              Quer ver dados reais do seu setor?
            </h3>
            <p className="text-sm text-ink-secondary mt-1">
              Deixe seu email e veja gratuitamente uma previa com 3 indicadores
              do diagnostico do mercado.
            </p>
          </div>
          <ContextualCaptureForm onSubmit={handleEmailSubmit} />
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Inner form (encapsulated to avoid polluting the parent)
// ---------------------------------------------------------------------------

function ContextualCaptureForm({
  onSubmit,
}: {
  onSubmit: (email: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!email || loading) return;

      setLoading(true);
      setError("");
      try {
        const res = await fetch("/api/lead-capture", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, source: "contextual-capture-blog" }),
        });

        if (res.ok) {
          onSubmit(email);
        } else {
          const errData = await res.json().catch(() => ({}));
          setError(
            (errData as { detail?: string }).detail ??
              "Erro ao registrar. Tente novamente.",
          );
        }
      } catch {
        setError("Erro de conexao. Tente novamente.");
      } finally {
        setLoading(false);
      }
    },
    [email, loading, onSubmit],
  );

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col sm:flex-row gap-2 w-full sm:w-auto shrink-0"
    >
      <input
        type="email"
        required
        placeholder="seu@email.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="px-4 py-2.5 rounded-lg border border-border bg-surface-0 text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-blue text-sm min-w-[200px]"
        autoComplete="email"
        data-testid="contextual-capture-email-input"
      />
      <button
        type="submit"
        disabled={loading}
        className="px-5 py-2.5 bg-brand-blue text-white font-semibold rounded-lg text-sm hover:bg-brand-blue-hover transition-colors disabled:opacity-50 whitespace-nowrap"
        data-testid="contextual-capture-submit"
      >
        {loading ? "Enviando..." : "Ver diagnostico gratuito"}
      </button>
      {error && (
        <p className="mt-1 text-sm text-red-600 sm:absolute sm:mt-10" role="alert">
          {error}
        </p>
      )}
    </form>
  );
}
