"use client";

import { useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { ViabilityFactors } from "../../../components/ViabilityBadge";
import { formatCurrencyBR } from "../../../lib/format-currency";

// ---------------------------------------------------------------------------
// WhyThisOpportunity — "Por que esta oportunidade?" expandable section
// Shows a breakdown of viability factors for each bid result card.
// VIAB-UX-004
// ---------------------------------------------------------------------------

export interface WhyThisOpportunityProps {
  viabilityScore?: number | null;
  viabilityLevel?: "alta" | "media" | "baixa" | null;
  viabilityFactors?: ViabilityFactors | null;
  sectorName?: string;
  matchedTerms?: string[];
  orgao?: string;
  municipio?: string;
  uf?: string;
  valor?: number | null;
  bidId?: string;
  isOpen: boolean;
  onToggle: () => void;
}

/** Score badge color based on value */
function getScoreColor(score: number): string {
  if (score >= 70) return "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300";
  if (score >= 40) return "bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300";
  return "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400";
}

/** Format confidence percentage from score */
function formatConfidence(score?: number | null): string {
  if (score == null) return "N/A";
  return `${score}%`;
}

export default function WhyThisOpportunity({
  viabilityScore,
  viabilityFactors,
  sectorName,
  matchedTerms,
  municipio,
  uf,
  valor,
  bidId,
  isOpen,
  onToggle,
}: WhyThisOpportunityProps) {
  // Track expansion in Mixpanel
  useEffect(() => {
    if (isOpen && bidId && typeof window !== "undefined" && window.mixpanel) {
      window.mixpanel.track("why_this_opportunity_expanded", { bid_id: bidId });
    }
  }, [isOpen, bidId]);

  const hasViabilityFactors = viabilityFactors != null;
  const hasKeywords = matchedTerms && matchedTerms.length > 0;

  return (
    <div className="mt-2" data-testid="why-this-opportunity">
      {/* Toggle button */}
      <button
        type="button"
        onClick={onToggle}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-muted hover:text-ink-secondary transition-colors group"
        aria-expanded={isOpen}
        data-testid="why-toggle-btn"
      >
        <svg
          className={`w-3.5 h-3.5 transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
        <span>Por que esta oportunidade?</span>
        {viabilityScore != null && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-surface-2 text-ink-muted ml-1">
            {formatConfidence(viabilityScore)}
          </span>
        )}
      </button>

      {/* Expandable content */}
      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="why-content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: "easeInOut" }}
            className="overflow-hidden"
            data-testid="why-content"
          >
            <div className="mt-2 p-3 bg-surface-1 rounded-lg border border-border">
              {/* Sector and Keywords */}
              <div className="space-y-2 mb-3">
                {sectorName && (
                  <p className="text-xs text-ink-secondary" data-testid="why-sector">
                    <span className="font-medium text-ink">Setor detectado:</span>{" "}
                    {sectorName}{" "}
                    {viabilityScore != null && (
                      <span className="text-ink-muted">
                        (confiança: {formatConfidence(viabilityScore)})
                      </span>
                    )}
                  </p>
                )}
                <p className="text-xs text-ink-secondary" data-testid="why-keywords">
                  <span className="font-medium text-ink">Keywords:</span>{" "}
                  {hasKeywords
                    ? matchedTerms.join(", ")
                    : "Detecção automática por IA"}
                </p>
              </div>

              {/* Factors grid */}
              {hasViabilityFactors && (
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {/* Prazo */}
                  {renderFactor(
                    "Prazo",
                    viabilityFactors!.timeline,
                    viabilityFactors!.timeline_label,
                    "calendar",
                  )}

                  {/* Valor */}
                  {renderFactor(
                    "Valor",
                    viabilityFactors!.value_fit,
                    valor != null
                      ? `${formatCurrencyBR(valor)} — ${viabilityFactors!.value_fit_label}`
                      : viabilityFactors!.value_fit_label,
                    "currency",
                  )}

                  {/* Local */}
                  {renderFactor(
                    "Local",
                    viabilityFactors!.geography,
                    municipio && uf
                      ? `${municipio}/${uf} — ${viabilityFactors!.geography_label}`
                      : viabilityFactors!.geography_label,
                    "location",
                  )}

                  {/* Modalidade */}
                  {renderFactor(
                    "Modalidade",
                    viabilityFactors!.modalidade,
                    viabilityFactors!.modalidade_label,
                    "document",
                  )}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** Render a single factor row with icon, label, description and score badge */
function renderFactor(
  name: string,
  score: number,
  description: string,
  iconType: "calendar" | "currency" | "location" | "document",
) {
  const icon = getFactorIcon(iconType);

  return (
    <div
      className="flex items-start gap-2 p-2 rounded-md bg-surface-0/50"
      data-testid={`why-factor-${name.toLowerCase()}`}
    >
      <span className="mt-0.5 shrink-0 text-ink-muted" aria-hidden="true">
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-[11px] font-medium text-ink">{name}</p>
        <p className="text-[10px] text-ink-secondary leading-relaxed line-clamp-2">
          {description}
        </p>
      </div>
      <span
        className={`shrink-0 inline-flex items-center justify-center min-w-[2rem] px-1.5 py-0.5 rounded text-[10px] font-semibold ${getScoreColor(score)}`}
        data-testid={`why-factor-${name.toLowerCase()}-score`}
      >
        {score}
      </span>
    </div>
  );
}

/** SVG icons for each factor type */
function getFactorIcon(type: "calendar" | "currency" | "location" | "document") {
  switch (type) {
    case "calendar":
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      );
    case "currency":
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case "location":
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      );
    case "document":
      return (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      );
  }
}
