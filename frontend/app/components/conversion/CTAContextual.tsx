'use client';

/**
 * CTAContextual — CONV-002
 *
 * A contextual CTA button/block that adapts to the page context.
 * Variants map to default text/link combinations:
 *   - trial: "Testar grátis por 7 dias" -> /signup?source=entity_{entityType}
 *   - report: "Comprar relatório completo" -> /checkout?sku=relatorio-{entityType}
 *   - search: "Buscar editais agora" -> /buscar
 *
 * Tracks click via Mixpanel: cta_contextual_click with { variant, entityType, entityName }.
 */

import React, { useCallback } from 'react';
import Link from 'next/link';

export type CTAVariant = 'trial' | 'report' | 'search';

export interface CTAContextualProps {
  /** CTA variant */
  variant: CTAVariant;
  /** Entity context for tracking */
  entityType: string;
  /** Entity name for personalization */
  entityName: string;
  /** Override CTA text */
  ctaText?: string;
  /** Override CTA link */
  ctaLink?: string;
}

interface VariantConfig {
  defaultText: string;
  defaultHref: (entityType: string) => string;
  showSecondary?: boolean;
}

const VARIANT_CONFIG: Record<CTAVariant, VariantConfig> = {
  trial: {
    defaultText: 'Testar grátis por 7 dias',
    defaultHref: (entityType: string) =>
      `/signup?source=entity_${entityType}`,
    showSecondary: true,
  },
  report: {
    defaultText: 'Comprar relatório completo',
    defaultHref: (entityType: string) =>
      `/checkout?sku=relatorio-${entityType}`,
  },
  search: {
    defaultText: 'Buscar editais agora',
    defaultHref: () => '/buscar',
  },
};

export default function CTAContextual({
  variant,
  entityType,
  entityName,
  ctaText,
  ctaLink,
}: CTAContextualProps) {
  const config = VARIANT_CONFIG[variant];
  const text = ctaText ?? config.defaultText;
  const href = ctaLink ?? config.defaultHref(entityType);

  const handleClick = useCallback(() => {
    if (typeof window !== 'undefined' && window.mixpanel) {
      window.mixpanel.track('cta_contextual_click', {
        variant,
        entityType,
        entityName,
      });
    }
  }, [variant, entityType, entityName]);

  return (
    <div className="my-8 text-center">
      <Link
        href={href}
        onClick={handleClick}
        data-testid="cta-contextual"
        className="inline-block w-full rounded-xl bg-green-600 px-8 py-3 text-center font-bold text-white shadow-lg transition-colors hover:bg-green-700 sm:w-auto"
      >
        {text}
      </Link>
      {config.showSecondary && (
        <p className="mt-2 text-sm text-gray-500">
          Sem compromisso. Cancele quando quiser.
        </p>
      )}
    </div>
  );
}
