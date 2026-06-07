"use client";

import { useState } from "react";
import type { components } from "../../api-types.generated";
import type { DigitalProductContext, PreviewVariant } from "./DigitalProductPreview";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DigitalProductOut = components["schemas"]["DigitalProductOut"];

export interface CheckoutButtonProps {
  /** Product data to display in the button label and pass to checkout. */
  product: DigitalProductOut;
  /** Context metadata forwarded to the checkout endpoint. */
  context: DigitalProductContext;
  /** Visual variant matching the parent preview. */
  variant?: PreviewVariant;
  /** Optional click handler fired before the modal opens. */
  onClick?: () => void;
  /** Optional callback fired after successful checkout (Stripe redirect). */
  onComplete?: () => void;
  /** Disable the button (e.g., while loading in parent). */
  disabled?: boolean;
  /** Override label text. Defaults to "Comprar por R$XX". */
  label?: string;
  /** Class name override. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Price formatting
// ---------------------------------------------------------------------------

function formatBRL(cents: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

// ---------------------------------------------------------------------------
// Variant-specific styles
// ---------------------------------------------------------------------------

const baseStyles =
  "inline-flex items-center justify-center font-semibold transition-all focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed";

const variantStyles: Record<PreviewVariant, string> = {
  inline:
    "w-full rounded-lg bg-brand-navy px-5 py-2.5 text-sm text-white hover:bg-brand-blue-hover focus:ring-brand-navy",
  card:
    "w-full rounded-xl bg-brand-navy px-6 py-3 text-base text-white hover:bg-brand-blue-hover hover:-translate-y-0.5 hover:shadow-lg focus:ring-brand-navy",
  banner:
    "rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-brand-navy hover:bg-white/90 focus:ring-white",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function CheckoutButton({
  product,
  context,
  variant = "card",
  onClick,
  onComplete,
  disabled = false,
  label,
  className = "",
}: CheckoutButtonProps) {
  const [loading, setLoading] = useState(false);

  const defaultLabel = `Comprar por ${formatBRL(product.price_brl)}`;
  const buttonLabel = label ?? defaultLabel;

  const handleClick = async () => {
    if (loading || disabled) return;

    setLoading(true);
    try {
      onClick?.();

      // Stripe Checkout redirect via backend
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
        // Try to extract error detail from backend
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
      onComplete?.();

      // Redirect to Stripe Checkout
      window.location.href = data.checkout_url;
    } catch (err) {
      setLoading(false);
      alert(
        err instanceof Error
          ? err.message
          : "Erro ao iniciar checkout. Tente novamente.",
      );
    }
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading || disabled}
      data-testid="checkout-button"
      className={`${baseStyles} ${variantStyles[variant]} ${className}`}
    >
      {loading ? (
        <span className="flex items-center gap-2">
          <svg
            className="animate-spin h-4 w-4"
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
          Aguarde...
        </span>
      ) : (
        buttonLabel
      )}
    </button>
  );
}
