"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { CheckoutButton } from "@/app/components/checkout";
import type { components } from "@/app/api-types.generated";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DigitalProductOut = components["schemas"]["DigitalProductOut"];

export interface PartialReportPreviewProps {
  /** 3 free preview items — shown with label + value. */
  previewData: { label: string; value: string }[];
  /** 5 blurred/premium items — only label is shown (value hidden). */
  blurredData: { label: string }[];
  /** Product SKU for the CheckoutButton. */
  productSku: string;
  /** Context forwarded to the checkout endpoint for tracking. */
  contextInfo: { entity_type: string; entity_id: string };
  /** If provided, skips the email capture gate. */
  preCapturedEmail?: string;
}

// ---------------------------------------------------------------------------
// Price formatting (hardcoded R$ 47 for the label)
// ---------------------------------------------------------------------------

const REPORT_PRICE = 4700; // cents

// ---------------------------------------------------------------------------
// Product fetch hook (inline, follows DigitalProductPreview pattern)
// ---------------------------------------------------------------------------

type LoadState = "idle" | "loading" | "loaded" | "error";

function useProduct(sku: string) {
  const [product, setProduct] = useState<DigitalProductOut | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");

  const fetchProduct = useCallback(async () => {
    if (!sku) return;
    setLoadState("loading");
    try {
      const res = await fetch("/api/products");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = (await res.json()) as { products: DigitalProductOut[] };
      const found = (data.products ?? []).find((p) => p.sku === sku);
      if (found) {
        setProduct(found);
      } else {
        // Fallback: create minimal product object so CheckoutButton still works
        setProduct({
          sku,
          price_brl: REPORT_PRICE,
          name: "Relatorio completo",
          description: null,
          delivery_config: {},
          preview_config: {},
        });
      }
      setLoadState("loaded");
    } catch {
      // On error, still provide a fallback so the CTA isn't broken
      setProduct({
        sku,
        price_brl: REPORT_PRICE,
        name: "Relatorio completo",
        description: null,
        delivery_config: {},
        preview_config: {},
      });
      setLoadState("loaded");
    }
  }, [sku]);

  useEffect(() => {
    fetchProduct();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { product, loadState };
}

// ---------------------------------------------------------------------------
// Minimal tracking helper
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

export function PartialReportPreview({
  previewData,
  blurredData,
  productSku,
  contextInfo,
  preCapturedEmail,
}: PartialReportPreviewProps) {
  const { product, loadState } = useProduct(productSku);
  const [email, setEmail] = useState(preCapturedEmail ?? "");
  const [emailSubmitted, setEmailSubmitted] = useState(!!preCapturedEmail);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const hasTrackedImpression = useRef(false);
  const hasTrackedSubmit = useRef(false);

  // Track impression on first render of the preview state
  useEffect(() => {
    if (emailSubmitted && !hasTrackedImpression.current) {
      hasTrackedImpression.current = true;
      trackEvent("partial_report_impression", contextInfo);
    }
  }, [emailSubmitted, contextInfo]);

  const handleEmailSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!email || submitting) return;

      setSubmitting(true);
      setSubmitError("");
      try {
        const res = await fetch("/api/lead-capture", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, source: "partial-report-blog" }),
        });

        if (res.ok) {
          if (!hasTrackedSubmit.current) {
            hasTrackedSubmit.current = true;
            trackEvent("partial_report_email_submit", {
              ...contextInfo,
              email_domain: email.split("@")[1] ?? "",
            });
          }
          setEmailSubmitted(true);
        } else {
          const errData = await res.json().catch(() => ({}));
          setSubmitError(
            (errData as { detail?: string }).detail ??
              "Erro ao registrar. Tente novamente.",
          );
        }
      } catch {
        setSubmitError("Erro de conexao. Tente novamente.");
      } finally {
        setSubmitting(false);
      }
    },
    [email, submitting, contextInfo],
  );

  const handleCtaClick = useCallback(() => {
    trackEvent("partial_report_cta_click", contextInfo);
  }, [contextInfo]);

  // ------------------------------------------------------------------
  // Email capture gate
  // ------------------------------------------------------------------
  if (!emailSubmitted) {
    return (
      <section
        className="not-prose my-8 sm:my-10 bg-brand-blue-subtle/50 dark:bg-brand-navy/10 rounded-lg p-5 sm:p-6 border border-brand-blue/15"
        data-testid="partial-report-email-gate"
      >
        <h3 className="text-lg font-semibold text-ink mb-1">
          Veja o diagnostico gratuito
        </h3>
        <p className="text-sm text-ink-secondary mb-4">
          Deixe seu email para acessar uma previa gratuita com dados reais
          do diagnostico do seu setor.
        </p>
        <form
          onSubmit={handleEmailSubmit}
          className="flex flex-col sm:flex-row gap-3"
        >
          <input
            type="email"
            required
            placeholder="seu@email.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1 px-4 py-2.5 rounded-lg border border-border bg-surface-0 text-ink placeholder:text-ink-muted focus:outline-none focus:ring-2 focus:ring-brand-blue text-sm"
            autoComplete="email"
            data-testid="partial-report-email-input"
          />
          <button
            type="submit"
            disabled={submitting}
            className="px-5 py-2.5 bg-brand-blue text-white font-semibold rounded-lg text-sm hover:bg-brand-blue-hover transition-colors disabled:opacity-50 whitespace-nowrap"
            data-testid="partial-report-email-submit"
          >
            {submitting ? "Enviando..." : "Ver diagnostico gratuito"}
          </button>
        </form>
        {submitError && (
          <p className="mt-2 text-sm text-red-600" role="alert">
            {submitError}
          </p>
        )}
      </section>
    );
  }

  // ------------------------------------------------------------------
  // Preview (3 free + 5 blurred items)
  // ------------------------------------------------------------------
  const ctDisabled = loadState !== "loaded";
  const productToUse = product;

  return (
    <section
      className="not-prose my-8 sm:my-10"
      data-testid="partial-report-preview"
    >
      <div className="rounded-xl border border-border bg-surface-0 p-5 sm:p-6 shadow-sm">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h3 className="text-lg font-semibold text-ink">
              Previa do Relatorio
            </h3>
            <p className="text-sm text-ink-secondary mt-0.5">
              Dados reais — veja 3 de {previewData.length + blurredData.length}{" "}
              indicadores analisados.
            </p>
          </div>
          <span className="shrink-0 text-right">
            <span className="text-2xl font-bold text-ink">R$ 47</span>
            <span className="block text-xs text-ink-muted">
              pagamento unico
            </span>
          </span>
        </div>

        {/* Free preview items */}
        <div className="space-y-1.5">
          {previewData.slice(0, 3).map((item, idx) => (
            <div
              key={`free-${idx}`}
              className="flex items-center justify-between rounded-lg bg-surface-1 px-3 py-2 text-sm"
              data-testid="preview-item-free"
            >
              <span className="text-ink">{item.label}</span>
              <span className="font-medium text-ink">{item.value}</span>
            </div>
          ))}
        </div>

        {/* Blurred items with gradient overlay */}
        <div className="mt-1.5 space-y-1.5 relative">
          {blurredData.slice(0, 5).map((item, idx) => (
            <div
              key={`blurred-${idx}`}
              className="flex items-center justify-between rounded-lg bg-surface-1 px-3 py-2 text-sm blur-sm select-none"
              data-testid="preview-item-blurred"
            >
              <span className="text-ink-muted">{item.label}</span>
              <span className="text-ink-muted">R$ •••</span>
            </div>
          ))}
          {/* Gradient overlay — fades the bottom of blurred section */}
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-surface-0/70 pointer-events-none rounded-lg" />
        </div>

        {/* CTA */}
        <div className="mt-4">
          {productToUse ? (
            <CheckoutButton
              product={productToUse}
              context={{
                entity_type: contextInfo.entity_type,
                entity_id: contextInfo.entity_id,
              }}
              variant="inline"
              onClick={handleCtaClick}
            />
          ) : (
            <button
              type="button"
              disabled={ctDisabled}
              onClick={handleCtaClick}
              className="w-full rounded-lg bg-brand-navy px-5 py-2.5 text-sm text-white font-semibold hover:bg-brand-blue-hover transition-all disabled:opacity-60"
              data-testid="partial-report-fallback-cta"
            >
              {ctDisabled ? "Carregando..." : "Comprar por R$ 47"}
            </button>
          )}
        </div>

        {/* Metadata */}
        <div className="mt-3 flex items-center gap-4 text-xs text-ink-muted">
          <span>{previewData.length + blurredData.length} indicadores</span>
          <span>Dados atualizados</span>
        </div>
      </div>
    </section>
  );
}
