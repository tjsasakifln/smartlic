"use client";

import { useState, useEffect, useCallback } from "react";
import type { components } from "../../api-types.generated";
import type { DigitalProductContext } from "./DigitalProductPreview";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DigitalProductOut = components["schemas"]["DigitalProductOut"];

export interface CheckoutModalProps {
  /** Whether the modal is visible. */
  isOpen: boolean;
  /** Called when the user dismisses the modal. */
  onClose: () => void;
  /** Product being purchased. */
  product: DigitalProductOut;
  /** Context metadata forwarded to the checkout endpoint. */
  context: DigitalProductContext;
  /** Optional callback fired after successful checkout initiation (Stripe redirect). */
  onComplete?: () => void;
}

type CheckoutStatus = "idle" | "loading" | "error" | "success" | "redirecting";

// ---------------------------------------------------------------------------
// Price formatting
// ---------------------------------------------------------------------------

function formatBRL(cents: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 2,
  }).format(cents / 100);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function trackEvent(name: string, props?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  const mp = (
    window as unknown as { mixpanel?: { track: (e: string, p?: Record<string, unknown>) => void } }
  ).mixpanel;
  if (!mp) return;
  try {
    mp.track(name, props ?? {});
  } catch {
    // best-effort
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CheckoutModal({
  isOpen,
  onClose,
  product,
  context,
  onComplete,
}: CheckoutModalProps) {
  const [status, setStatus] = useState<CheckoutStatus>("idle");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  // Track modal view
  useEffect(() => {
    if (isOpen) {
      trackEvent("product_checkout_modal_viewed", {
        sku: product.sku,
        price_brl: product.price_brl,
        ...context,
      });
    }
  }, [isOpen, product.sku, product.price_brl, context]);

  // Handle Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // Focus trap — focus first interactive element
  useEffect(() => {
    if (!isOpen) return;
    const timer = setTimeout(() => {
      const firstFocusable = document.querySelector<HTMLElement>(
        '[data-checkout-modal] button, [data-checkout-modal] a, [data-checkout-modal] input',
      );
      firstFocusable?.focus();
    }, 50);
    return () => clearTimeout(timer);
  }, [isOpen]);

  const handleStartCheckout = useCallback(async () => {
    if (status === "loading") return;

    setStatus("loading");
    setErrorMsg(null);

    trackEvent("product_checkout_started", {
      sku: product.sku,
      price_brl: product.price_brl,
      ...context,
    });

    try {
      const res = await fetch("/api/checkout/digital-product", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          sku: product.sku,
          context: {
            entity_type: context.entity_type ?? "",
            entity_id: context.entity_id ?? "",
            ...(context.setor ? { setor: context.setor } : {}),
            ...(context.uf ? { uf: context.uf } : {}),
          },
        }),
      });

      if (!res.ok) {
        let detail = "Nao foi possivel iniciar o checkout.";
        try {
          const errData = await res.json();
          if (typeof errData?.detail === "string") {
            detail = errData.detail;
          }
        } catch {
          // keep default
        }
        throw new Error(detail);
      }

      const data = (await res.json()) as { checkout_url: string };
      setStatus("redirecting");
      onComplete?.();

      trackEvent("product_checkout_redirected", {
        sku: product.sku,
        price_brl: product.price_brl,
      });

      // Redirect to Stripe Checkout
      window.location.href = data.checkout_url;
    } catch (err) {
      setStatus("error");
      setErrorMsg(
        err instanceof Error
          ? err.message
          : "Erro ao iniciar checkout. Tente novamente.",
      );
    }
  }, [status, product.sku, product.price_brl, context, onComplete]);

  if (!isOpen) return null;

  // ---------- Success state ----------
  if (status === "success") {
    return (
      <div
        data-checkout-modal
        className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
        role="dialog"
        aria-modal="true"
        aria-labelledby="checkout-modal-success-title"
      >
        <div className="max-w-md w-full rounded-2xl bg-[var(--surface-0)] p-8 shadow-xl">
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100">
              <svg
                className="h-8 w-8 text-emerald-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            </div>
            <h2
              id="checkout-modal-success-title"
              className="text-xl font-bold text-[var(--ink)]"
            >
              Compra confirmada!
            </h2>
            <p className="mt-2 text-sm text-[var(--ink-secondary)]">
              Seu pagamento foi processado com sucesso. Voce recebera as
              instrucoes de acesso por email.
            </p>
            <button
              type="button"
              onClick={onClose}
              className="mt-6 w-full rounded-xl bg-brand-navy px-6 py-3 font-semibold text-white hover:bg-brand-blue-hover transition-colors focus:outline-none focus:ring-2 focus:ring-brand-navy focus:ring-offset-2"
            >
              Continuar
            </button>
          </div>
        </div>
      </div>
    );
  }

  // ---------- Main modal ----------
  return (
    <div
      data-checkout-modal
      className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="checkout-modal-title"
    >
      <div className="max-w-md w-full rounded-2xl bg-[var(--surface-0)] p-6 shadow-xl max-h-[90vh] overflow-y-auto">
        {/* Close button */}
        <div className="flex items-center justify-between mb-6">
          <h2 id="checkout-modal-title" className="text-lg font-bold text-[var(--ink)]">
            Finalizar compra
          </h2>
          <button
            type="button"
            onClick={onClose}
            disabled={status === "loading" || status === "redirecting"}
            className="p-1.5 rounded-full text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-1)] transition-colors focus:outline-none focus:ring-2 focus:ring-brand-navy"
            aria-label="Fechar modal"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Product summary */}
        <div className="rounded-xl bg-[var(--surface-1)] p-4 mb-6">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-[var(--ink)]">{product.name}</p>
              {product.description && (
                <p className="mt-1 text-sm text-[var(--ink-secondary)]">
                  {product.description}
                </p>
              )}
            </div>
            <span className="shrink-0 text-lg font-bold text-brand-navy">
              {formatBRL(product.price_brl)}
            </span>
          </div>
          <p className="mt-2 text-xs text-[var(--ink-muted)]">
            Pagamento unico via Stripe (cartao, boleto ou PIX)
          </p>
        </div>

        {/* Context info */}
        {context.entity_type && context.entity_id && (
          <div className="mb-4 text-xs text-[var(--ink-muted)]">
            Produto para: {context.entity_type} {context.entity_id}
            {context.setor && ` / ${context.setor}`}
            {context.uf && ` / ${context.uf}`}
          </div>
        )}

        {/* Error state */}
        {status === "error" && errorMsg && (
          <div
            role="alert"
            className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-800"
          >
            {errorMsg}
          </div>
        )}

        {/* Confirm button */}
        <button
          type="button"
          onClick={handleStartCheckout}
          disabled={status === "loading" || status === "redirecting"}
          data-testid="checkout-modal-confirm"
          className="w-full rounded-xl bg-brand-navy px-6 py-3.5 font-semibold text-white text-base hover:bg-brand-blue-hover transition-colors disabled:opacity-60 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-brand-navy focus:ring-offset-2"
        >
          {status === "loading" || status === "redirecting" ? (
            <span className="flex items-center justify-center gap-2">
              <svg
                className="animate-spin h-5 w-5"
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
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              {status === "redirecting"
                ? "Redirecionando para pagamento..."
                : "Processando..."}
            </span>
          ) : (
            `Confirmar compra — ${formatBRL(product.price_brl)}`
          )}
        </button>

        {/* Confidence footer */}
        <div className="mt-4 flex flex-wrap items-center justify-center gap-4 text-xs text-[var(--ink-muted)]">
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5 text-emerald-500" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
            Pagamento 100% seguro
          </span>
          <span className="flex items-center gap-1">
            <svg className="w-3.5 h-3.5 text-blue-500" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
              <path fillRule="evenodd" d="M2.166 4.999A11.954 11.954 0 0010 1.944 11.954 11.954 0 0017.834 5C18.577 6.44 19 8.027 19 9.7c0 5.009-3.667 9.132-8.44 9.878a.75.75 0 01-.12.002.75.75 0 01-.12-.002C5.667 18.832 2 14.709 2 9.7c0-1.673.423-3.26 1.166-4.701zM10 5a1 1 0 011 1v3.586l2.207 2.207a1 1 0 01-1.414 1.414l-2.5-2.5A1 1 0 019 10V6a1 1 0 011-1z" clipRule="evenodd" />
            </svg>
            Garantia 30 dias
          </span>
        </div>
      </div>
    </div>
  );
}
