"use client";

/**
 * SectorUfIntelReportCTA — Issue #633: Mapa de Oportunidade Setorial (R$47)
 *
 * First microtransaction CTA for sector/UF entity pages.
 * Wraps DigitalProductPreview with sector/UF-specific context, tracking,
 * and a custom checkout label.
 *
 * Usage:
 *   <SectorUfIntelReportCTA sectorName="limpeza" uf="SP" variant="inline" />
 */

import { useEffect, useCallback } from "react";
import {
  DigitalProductPreview,
  type PreviewVariant,
} from "./checkout/DigitalProductPreview";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SectorUfIntelReportCTAProps {
  /** Sector slug (e.g. "limpeza", "pavimentacao-asfaltica") */
  sectorName: string;
  /** 2-letter UF code (e.g. "SP", "RJ") */
  uf: string;
  /** Visual variant matching DigitalProductPreview. Default: "inline" */
  variant?: PreviewVariant;
  /** Optional override for the checkout button label. Default: "Mapa Completo deste Setor — R$47" */
  checkoutLabel?: string;
  /** Class name override for the outermost container. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * SKU for the "Mapa de Oportunidade Setorial" product seeded in the
 * digital_products table. Price: R$47 (4700 BRL cents).
 */
const SKU = "mapa-oportunidade-setorial";

const DEFAULT_CHECKOUT_LABEL = "Mapa Completo deste Setor — R$47";

// ---------------------------------------------------------------------------
// Mixpanel tracking helper
// ---------------------------------------------------------------------------

function trackEvent(name: string, props?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  const mp = (
    window as unknown as {
      mixpanel?: { track: (e: string, p?: Record<string, unknown>) => void };
    }
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

export default function SectorUfIntelReportCTA({
  sectorName,
  uf,
  variant = "inline",
  checkoutLabel = DEFAULT_CHECKOUT_LABEL,
  className = "",
}: SectorUfIntelReportCTAProps) {
  // Track impression once on mount
  useEffect(() => {
    trackEvent("sector_uf_cta_impression", {
      sector_id: sectorName,
      uf,
      variant,
      sku: SKU,
    });
  }, [sectorName, uf, variant]);

  // Track click when checkout starts
  const handleCheckoutStart = useCallback(() => {
    trackEvent("sector_uf_cta_click", {
      sector_id: sectorName,
      uf,
      variant,
      sku: SKU,
    });
  }, [sectorName, uf, variant]);

  return (
    <DigitalProductPreview
      sku={SKU}
      context={{
        entity_type: "setor",
        entity_id: `${sectorName}:${uf}`,
        setor: sectorName,
        uf,
      }}
      variant={variant}
      checkoutLabel={checkoutLabel}
      onCheckoutStart={handleCheckoutStart}
      className={className}
    />
  );
}
