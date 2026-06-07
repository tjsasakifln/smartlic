"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { components } from "../../api-types.generated";
import { CheckoutButton } from "./CheckoutButton";
import { CheckoutModal } from "./CheckoutModal";
import { GlassCard } from "../ui/GlassCard";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type DigitalProductOut = components["schemas"]["DigitalProductOut"];
type ProductsResponse = components["schemas"]["ProductsResponse"];

export interface DigitalProductContext {
  /** Entity type hosting the preview — "fornecedor", "orgao", "setor", etc. */
  entity_type?: string;
  /** Entity identifier (CNPJ, slug, sector_id, etc.) */
  entity_id?: string;
  /** Optional sector ID for context-aware filtering */
  setor?: string;
  /** Optional UF for location-aware filtering */
  uf?: string;
}

export type PreviewVariant = "inline" | "card" | "banner";

export interface DigitalProductPreviewProps {
  /** Product SKU to display and offer for purchase. */
  sku: string;
  /** Context metadata forwarded to the checkout endpoint. */
  context: DigitalProductContext;
  /** Visual variant: inline (entity pages), card (catalog), banner (blog). */
  variant?: PreviewVariant;
  /** Optional override for inline variant: inline elements are skipped inside
   *  a wrapping card; set `noWrapper={true}` if the parent already provides one. */
  noWrapper?: boolean;
  /** Class name override for the outermost container. */
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
// Preview items generator (configurable via preview_config)
// ---------------------------------------------------------------------------

interface PreviewItem {
  id: string;
  label: string;
  value: string;
  premium: boolean;
}

function generatePreviewItems(
  previewConfig: Record<string, unknown>,
): PreviewItem[] {
  const freeItems = (previewConfig.free_items as number) ?? 3;
  const totalItems = (previewConfig.total_items as number) ?? 8;
  const labels = (previewConfig.item_labels as string[]) ?? [
    "Secretaria de Educação",
    "Secretaria de Saúde",
    "Prefeitura Municipal",
    "Governo do Estado",
    "Ministério Público",
    "Câmara Municipal",
    "Defensoria Pública",
    "Tribunal de Justiça",
  ];

  const items: PreviewItem[] = [];
  for (let i = 0; i < Math.min(totalItems, labels.length); i++) {
    const estimatedValue = (i + 1) * 150000;
    items.push({
      id: `preview-${i}`,
      label: labels[i],
      value: new Intl.NumberFormat("pt-BR", {
        style: "currency",
        currency: "BRL",
        maximumFractionDigits: 0,
      }).format(estimatedValue),
      premium: i >= freeItems,
    });
  }
  return items;
}

// ---------------------------------------------------------------------------
// Product fetch hook
// ---------------------------------------------------------------------------

type LoadState = "idle" | "loading" | "loaded" | "error";

function useProduct(sku: string) {
  const [product, setProduct] = useState<DigitalProductOut | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("idle");
  const [loadError, setLoadError] = useState<string | null>(null);

  const fetchProduct = useCallback(async () => {
    if (!sku) return;
    setLoadState("loading");
    setLoadError(null);
    try {
      const res = await fetch("/api/products");
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as ProductsResponse;
      const found = (data.products ?? []).find((p) => p.sku === sku);
      if (!found) {
        throw new Error(`Produto "${sku}" nao encontrado.`);
      }
      setProduct(found);
      setLoadState("loaded");
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Erro ao carregar produto.";
      setLoadError(msg);
      setLoadState("error");
    }
  }, [sku]);

  useEffect(() => {
    fetchProduct();
  }, [fetchProduct]);

  return { product, loadState, loadError, refetch: fetchProduct };
}

// ---------------------------------------------------------------------------
// Variant styles
// ---------------------------------------------------------------------------

const variantStyles: Record<
  PreviewVariant,
  {
    container: string;
    heading: string;
    description: string;
    price: string;
  }
> = {
  inline: {
    container:
      "rounded-xl border border-[var(--border)] bg-[var(--surface-0)] p-5",
    heading: "text-lg font-semibold text-[var(--ink)]",
    description: "text-sm text-[var(--ink-secondary)] mt-1",
    price: "text-2xl font-bold text-[var(--ink)]",
  },
  card: {
    container:
      "rounded-2xl border border-[var(--border)] bg-[var(--surface-0)] p-6 shadow-sm hover:shadow-md transition-shadow",
    heading: "text-xl font-bold text-[var(--ink)]",
    description: "text-sm text-[var(--ink-secondary)] mt-2",
    price: "text-3xl font-bold text-[var(--ink)]",
  },
  banner: {
    container:
      "rounded-xl bg-gradient-to-r from-[var(--brand-navy)] to-[var(--brand-blue)] p-6 text-white",
    heading: "text-xl font-bold text-white",
    description: "text-sm text-white/80 mt-1",
    price: "text-3xl font-bold text-white",
  },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function DigitalProductPreview({
  sku,
  context,
  variant = "card",
  noWrapper = false,
  className = "",
}: DigitalProductPreviewProps) {
  const { product, loadState, loadError, refetch } = useProduct(sku);
  const [showModal, setShowModal] = useState(false);

  // --- Tracking helpers (defined above early returns so hooks order is stable) ---
  const trackEventInternal = (name: string, extra?: Record<string, unknown>) => {
    if (typeof window === "undefined") return;
    const mp = (
      window as unknown as { mixpanel?: { track: (e: string, p?: Record<string, unknown>) => void } }
    ).mixpanel;
    if (!mp) return;
    try {
      mp.track(name, {
        ...(product ? { sku: product.sku, price_brl: product.price_brl } : {}),
        ...context,
        ...extra,
      });
    } catch {
      // best-effort
    }
  };

  // Track view when product data is loaded (fires once)
  const hasTrackedView = useRef(false);
  useEffect(() => {
    if (product && !hasTrackedView.current) {
      hasTrackedView.current = true;
      trackEventInternal("product_preview_viewed", { source_template: variant });
    }
  });

  // --- Loading state ---
  if (loadState === "loading") {
    return (
      <div
        className={`animate-pulse ${variantStyles[variant].container} ${className}`}
        data-testid="digital-product-preview-loading"
      >
        <div className="h-5 w-2/3 rounded bg-[var(--surface-1)]" />
        <div className="mt-2 h-4 w-full rounded bg-[var(--surface-1)]" />
        <div className="mt-4 h-8 w-1/3 rounded bg-[var(--surface-1)]" />
      </div>
    );
  }

  // --- Error state ---
  if (loadState === "error") {
    return (
      <div
        className={`rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800 ${className}`}
        role="alert"
        data-testid="digital-product-preview-error"
      >
        <p className="font-medium">Produto indisponivel</p>
        <p className="mt-1 text-red-600">{loadError}</p>
        <button
          type="button"
          onClick={refetch}
          className="mt-2 text-sm font-medium text-red-700 underline hover:text-red-900"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  // --- Empty / not found ---
  if (!product) {
    return null;
  }

  const previewItems = generatePreviewItems(
    (product.preview_config as Record<string, unknown>) ?? {},
  );
  const styles = variantStyles[variant];
  const isBanner = variant === "banner";

  const handleCheckoutStart = () => {
    trackEventInternal("product_checkout_started", { source_template: variant });
    setShowModal(true);
  };

  const handleCheckoutComplete = () => {
    trackEventInternal("product_checkout_completed", { source_template: variant });
  };

  // ------------------------------------------------------------------
  // Preview items section
  // ------------------------------------------------------------------

  const previewSection = (
    <section aria-label="Previa do produto" className="space-y-1.5">
      {previewItems.map((item) => (
        <div
          key={item.id}
          data-testid={`preview-item-${item.premium ? "premium" : "free"}-${item.id}`}
          className={`flex items-center justify-between rounded-lg px-3 py-2 text-sm ${
            item.premium
              ? "relative overflow-hidden blur-sm select-none"
              : "bg-[var(--surface-1)]"
          }`}
        >
          <span
            className={
              item.premium ? "text-[var(--ink-muted)]" : "text-[var(--ink)]"
            }
          >
            {item.label}
          </span>
          <span
            className={
              item.premium
                ? "text-[var(--ink-muted)]"
                : "font-medium text-[var(--ink)]"
            }
          >
            {item.value}
          </span>
          {item.premium && (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="rounded bg-[var(--surface-0)]/80 px-2 py-0.5 text-xs font-medium text-[var(--ink-muted)]">
                Premium
              </span>
            </div>
          )}
        </div>
      ))}
    </section>
  );

  // ---------- Banner variant ----------
  if (isBanner) {
    return (
      <>
        <div
          className={`flex items-center justify-between gap-4 ${styles.container} ${className}`}
          data-testid="digital-product-preview-banner"
        >
          <div className="flex-1 min-w-0">
            <h3 className={styles.heading}>{product.name}</h3>
            {product.description && (
              <p className={styles.description}>{product.description}</p>
            )}
            <p className="mt-1 text-sm text-white/60">
              {previewItems.length} itens analisados —{" "}
              {previewItems.filter((i) => i.premium).length} exclusivos
            </p>
          </div>
          <div className="flex items-center gap-4 shrink-0">
            <span className={styles.price}>
              {formatBRL(product.price_brl)}
            </span>
            <CheckoutButton
              product={product}
              context={context}
              variant="banner"
              onClick={handleCheckoutStart}
              onComplete={handleCheckoutComplete}
            />
          </div>
        </div>

        <CheckoutModal
          isOpen={showModal}
          onClose={() => setShowModal(false)}
          product={product}
          context={context}
          onComplete={handleCheckoutComplete}
        />
      </>
    );
  }

  // ---------- Inline / Card variants ----------
  const content = (
    <div
      className={`${styles.container} ${className}`}
      data-testid={`digital-product-preview-${variant}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className={styles.heading}>{product.name}</h3>
          {product.description && (
            <p className={styles.description}>{product.description}</p>
          )}
        </div>
        <span className="shrink-0 text-right">
          <span className={styles.price}>
            {formatBRL(product.price_brl)}
          </span>
          <span className="block text-xs text-[var(--ink-muted)]">
            pagamento unico
          </span>
        </span>
      </div>

      {/* Preview items */}
      <div className="mt-4">{previewSection}</div>

      {/* CTA */}
      <div className="mt-4">
        <CheckoutButton
          product={product}
          context={context}
          variant={variant}
          onClick={handleCheckoutStart}
          onComplete={handleCheckoutComplete}
        />
      </div>

      {/* Metadata */}
      <div className="mt-3 flex items-center gap-4 text-xs text-[var(--ink-muted)]">
        <span>{previewItems.length} itens no total</span>
        <span>Estimativa atualizada</span>
      </div>
    </div>
  );

  return (
    <>
      {noWrapper ? content : variant === "card" ? <GlassCard hoverable={false}>{content}</GlassCard> : content}
      <CheckoutModal
        isOpen={showModal}
        onClose={() => setShowModal(false)}
        product={product}
        context={context}
        onComplete={handleCheckoutComplete}
      />
    </>
  );
}
