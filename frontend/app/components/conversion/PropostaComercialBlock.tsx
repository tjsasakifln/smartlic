"use client";

/**
 * PropostaComercialBlock — Issue #1402 (CONV-010-1)
 *
 * Reusable "Proposta Comercial" block for entity pages (fornecedor, orgao, setor,
 * municipio, contrato). Receives entity data as props and renders:
 *   - Dynamic headline with entity name interpolation
 *   - 2-3 insight cards with real data from the entity
 *   - Contextual CTA button
 *
 * Uses `proposal-mapping.ts` for config per entity type.
 *
 * Responsive: single-column on mobile, multi-column on sm+.
 */

import React, { useMemo } from "react";
import Link from "next/link";
import {
  getProposalConfig,
  formatInsightValue,
  type EntityType,
  type InsightConfig,
} from "./proposal-mapping";

export interface PropostaComercialBlockProps {
  pageType: EntityType;
  entityName: string;
  /** Raw entity data (e.g. FornecedorProfile, OrgaoStats) used to extract insight values */
  entityData: Record<string, unknown>;
  /** Optional SKU override for CTA link */
  ctaSku?: string;
  className?: string;
}

interface InsightCard {
  id: string;
  icon: string;
  label: string;
  value: string;
}

/**
 * Extract a value from a nested object using a dot-separated accessor path.
 * Example: extractValue({ a: { b: 42 } }, "a.b") => 42
 */
function extractValue(
  data: Record<string, unknown>,
  accessor: string,
): unknown {
  const parts = accessor.split(".");
  let current: unknown = data;
  for (const part of parts) {
    if (current === null || current === undefined) return undefined;
    if (typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[part];
  }
  return current;
}

export function PropostaComercialBlock({
  pageType,
  entityName,
  entityData,
  ctaSku,
  className = "",
}: PropostaComercialBlockProps) {
  const config = useMemo(() => getProposalConfig(pageType), [pageType]);

  const headline = useMemo(
    () => config.headline.replace(/\{\{name\}\}/g, entityName),
    [config.headline, entityName],
  );

  const insightCards: InsightCard[] = useMemo(
    () =>
      config.insights
        .map((insight: InsightConfig) => {
          const raw = extractValue(entityData, insight.accessor);
          const formatted = formatInsightValue(raw, insight.format);
          const displayValue = formatted || insight.fallback;
          return { id: insight.id, icon: insight.icon, label: insight.label, value: displayValue };
        })
        .filter((card) => card.value.length > 0),
    [config.insights, entityData],
  );

  const ctaHref = ctaSku
    ? `/signup?ref=proposta-${pageType}&sku=${ctaSku}`
    : config.cta.href;

  return (
    <section
      className={`w-full rounded-2xl border border-blue-100 bg-gradient-to-br from-blue-50 via-white to-indigo-50 p-6 dark:border-blue-800/40 dark:from-blue-950/20 dark:via-gray-900 dark:to-indigo-950/20 sm:p-8 ${className}`}
      data-testid="proposta-comercial-block"
      data-page-type={pageType}
    >
      <div className="mx-auto max-w-3xl">
        {/* Headline */}
        <h2 className="mb-3 text-2xl font-bold text-gray-900 dark:text-white sm:text-3xl">
          {headline}
        </h2>

        {/* Subtitle */}
        <p className="mb-6 text-base text-gray-600 dark:text-gray-300 sm:text-lg">
          {config.subtitle}
        </p>

        {/* Insight Cards */}
        {insightCards.length > 0 && (
          <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {insightCards.map((card) => (
              <div
                key={card.id}
                className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800"
                data-testid={`insight-card-${card.id}`}
              >
                <div className="mb-2 text-2xl" aria-hidden="true">
                  {card.icon}
                </div>
                <p className="mb-1 text-xs uppercase tracking-wider text-gray-500 dark:text-gray-400">
                  {card.label}
                </p>
                <p className="text-lg font-semibold text-gray-900 dark:text-white">
                  {card.value}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* CTA buttons */}
        <div className="flex flex-col gap-3 sm:flex-row">
          <Link
            href={ctaHref}
            data-testid="proposta-cta-primary"
            className="inline-flex min-h-[48px] items-center justify-center rounded-lg bg-blue-600 px-6 py-3 text-center font-semibold text-white transition-colors hover:bg-blue-700"
          >
            {config.cta.label}
          </Link>
          {config.cta.secondaryLabel && config.cta.secondaryHref && (
            <Link
              href={config.cta.secondaryHref}
              data-testid="proposta-cta-secondary"
              className="inline-flex min-h-[48px] items-center justify-center rounded-lg border border-gray-300 bg-white px-6 py-3 text-center font-medium text-gray-700 transition-colors hover:border-blue-400 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
            >
              {config.cta.secondaryLabel}
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}

export default PropostaComercialBlock;
