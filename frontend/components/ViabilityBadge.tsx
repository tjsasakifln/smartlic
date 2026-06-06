"use client";

import React, { useState, useRef, useCallback, useEffect, useId } from "react";
import mixpanel from "mixpanel-browser";

/** D-04 AC1: Viability factor breakdown */
export interface ViabilityFactors {
  modalidade: number;
  modalidade_label: string;
  timeline: number;
  timeline_label: string;
  value_fit: number;
  value_fit_label: string;
  geography: number;
  geography_label: string;
}

interface ViabilityBadgeProps {
  level?: "alta" | "media" | "baixa" | null;
  score?: number | null;
  factors?: ViabilityFactors | null;
  valueSource?: "estimated" | "missing" | null;
  /** VIAB-UX-002: Bid identifier for Mixpanel analytics tracking */
  bidId?: string;
}

/** Factor line for data-tooltip-content text summary */
function factorLine(name: string, weight: string, score: number, label: string): string {
  return `${name} (${weight}): ${label} (${score}/100)`;
}

/** Progress bar color class based on score range: green >=70, yellow 40-69, gray <40 */
function barColor(score: number): string {
  if (score >= 70) return "bg-emerald-400";
  if (score >= 40) return "bg-yellow-400";
  return "bg-gray-400";
}

/** Progress bar background color class based on score range */
function barBgColor(score: number): string {
  if (score >= 70) return "bg-emerald-900/40";
  if (score >= 40) return "bg-yellow-900/40";
  return "bg-gray-700";
}

/** VIAB-UX-003: Individual factor row with label, score, weight, contextual explanation, and progress bar */
function FactorRow({
  name,
  weight,
  score,
  label,
}: {
  name: string;
  weight: string;
  score: number;
  label: string;
}) {
  return (
    <div className="text-gray-300" role="group" aria-label={`${name} ${weight}`}>
      <div className="flex items-baseline justify-between">
        <span className="text-white text-[10px] font-medium">
          {name}
          <span className="text-gray-400 font-normal"> {weight}</span>
        </span>
        <span className="text-[10px] tabular-nums">{score}/100</span>
      </div>
      <div className="text-[9px] text-gray-400/80 mt-0.5 mb-1 leading-tight line-clamp-2">
        {label}
      </div>
      <div className={`h-1.5 rounded-full w-full ${barBgColor(score)}`}>
        <div
          className={`h-full rounded-full ${barColor(score)}`}
          style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
          role="progressbar"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`${name}: ${score} de 100`}
        />
      </div>
    </div>
  );
}

/** D-04 AC8: Viability badge with accessible tooltip showing factor breakdown
 * DEBT-FE-002: Replaces non-accessible title attribute with keyboard+touch tooltip (WCAG 2.1 AA)
 */
export default function ViabilityBadge({
  level,
  score,
  factors,
  valueSource,
  bidId,
}: ViabilityBadgeProps) {
  if (!level) return null;

  const config: Record<
    string,
    {
      label: string;
      ariaLabel: string;
      bg: string;
      /** DEBT-FE-018: Level-specific icon for WCAG 1.4.1 (Use of Color) compliance */
      icon: React.ReactNode;
    }
  > = {
    alta: {
      label: "Viabilidade alta",
      ariaLabel: "Viabilidade alta para sua empresa",
      bg: "bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-300",
      icon: (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
        </svg>
      ),
    },
    media: {
      label: "Viabilidade média",
      ariaLabel: "Viabilidade média para sua empresa",
      bg: "bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300",
      icon: (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M12 3l9.66 16.59A1 1 0 0120.66 21H3.34a1 1 0 01-.86-1.41L12 3z" />
        </svg>
      ),
    },
    baixa: {
      label: "Viabilidade baixa",
      ariaLabel: "Viabilidade baixa para sua empresa",
      bg: "bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400",
      icon: (
        <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      ),
    },
  };

  const c = config[level] ?? config["baixa"];
  if (!c) return null;

  // Build tooltip text for data attribute (test introspection)
  const tooltipLines: string[] = [`Viabilidade: ${score ?? "?"}/100`];
  if (factors) {
    tooltipLines.push(
      factorLine("Modalidade", "30%", factors.modalidade, factors.modalidade_label),
      factorLine("Prazo", "25%", factors.timeline, factors.timeline_label),
      factorLine("Valor", "25%", factors.value_fit, factors.value_fit_label),
      factorLine("UF", "20%", factors.geography, factors.geography_label),
    );
  }
  if (valueSource === "missing") {
    tooltipLines.push(
      "⚠ Valor estimado não informado pelo órgão — viabilidade pode ser maior",
    );
  }

  return (
    <ViabilityTooltip
      tooltipLines={tooltipLines}
      factors={factors}
      score={score}
      valueSource={valueSource}
      ariaLabel={c.ariaLabel}
      bg={c.bg}
      level={level}
      score={score}
      bidId={bidId}
    >
      {c.icon}
      {c.label}
    </ViabilityTooltip>
  );
}

/** DEBT-FE-002: Accessible tooltip wrapper
 * - Keyboard accessible (focusable trigger with role=img + aria-label)
 * - Mobile tap-to-toggle support
 * - ARIA: role="tooltip" + aria-describedby linkage
 * - Dismisses on Escape key and outside click
 * VIAB-UX-003: Rich content with progress bars and factor breakdown
 */
function ViabilityTooltip({
  children,
  tooltipLines,
  factors,
  score,
  valueSource,
  ariaLabel,
  bg,
  level,
  score,
  bidId,
}: {
  children: React.ReactNode;
  tooltipLines: string[];
  factors?: ViabilityFactors | null;
  score?: number | null;
  valueSource?: "estimated" | "missing" | null;
  ariaLabel: string;
  bg: string;
  level: string;
  score?: number | null;
  bidId?: string;
}) {
  const [open, setOpen] = useState(false);
  const tooltipId = useId();
  const triggerRef = useRef<HTMLSpanElement>(null);
  /** VIAB-UX-002: Debounce ref to avoid duplicate Mixpanel events */
  const lastTrackedRef = useRef(0);

  /** VIAB-UX-002: Track viability_breakdown_viewed with dedup */
  const trackBreakdownViewed = useCallback(() => {
    const now = Date.now();
    if (now - lastTrackedRef.current < 500) return;
    lastTrackedRef.current = now;
    try {
      mixpanel.track("viability_breakdown_viewed", {
        bid_id: bidId,
        viability_score: score ?? null,
        timestamp: new Date().toISOString(),
        environment: process.env.NODE_ENV || "development",
      });
    } catch {
      // analytics failure is non-critical
    }
  }, [bidId, score]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      setOpen(false);
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      setOpen((prev) => !prev);
    }
  }, []);

  /** VIAB-UX-002: Track viability_breakdown_viewed when tooltip opens via hover/focus */
  useEffect(() => {
    if (open) {
      trackBreakdownViewed();
    }
  }, [open, trackBreakdownViewed]);

  // Dismiss on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (triggerRef.current && !triggerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // tooltip text joined for data attribute (test introspection)
  const tooltipText = tooltipLines.join("\n");

  return (
    <span className="relative inline-flex">
      {/* Badge trigger — carries all semantic + accessibility attributes */}
      <span
        ref={triggerRef}
        role="img"
        aria-label={ariaLabel}
        aria-describedby={open ? tooltipId : undefined}
        tabIndex={0}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={handleKeyDown}
        onClick={() => setOpen((prev) => !prev)}
        className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold cursor-default
          focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1 focus-visible:ring-current
          ${bg}`}
        data-testid="viability-badge"
        data-viability-level={level}
        data-tooltip-content={tooltipText}
      >
        {children}
      </span>

      {/* Tooltip panel — WCAG role="tooltip", linked via aria-describedby */}
      {open && (
        <span
          id={tooltipId}
          role="tooltip"
          className={[
            "absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2",
            "w-max max-w-[260px]",
            "bg-gray-900 dark:bg-gray-800 text-white text-[10px] leading-relaxed",
            "rounded-md px-2.5 py-2 shadow-lg",
            "pointer-events-none",
          ].join(" ")}
        >
          {/* Total score */}
          <div className="font-semibold mb-2 text-white text-[11px]">
            Viabilidade: {score ?? "?"}/100
          </div>

          {/* Factor rows with progress bars — VIAB-UX-003 */}
          {factors && (
            <div className="space-y-2">
              <FactorRow
                name="Modalidade"
                weight="30%"
                score={factors.modalidade}
                label={factors.modalidade_label}
              />
              <FactorRow
                name="Prazo"
                weight="25%"
                score={factors.timeline}
                label={factors.timeline_label}
              />
              <FactorRow
                name="Valor"
                weight="25%"
                score={factors.value_fit}
                label={factors.value_fit_label}
              />
              <FactorRow
                name="UF"
                weight="20%"
                score={factors.geography}
                label={factors.geography_label}
              />
            </div>
          )}

          {/* Missing value warning */}
          {valueSource === "missing" && (
            <div className="mt-1.5 text-[9px] text-yellow-400 leading-tight">
              ⚠ Valor estimado não informado pelo órgão — viabilidade pode ser maior
            </div>
          )}

          {/* Arrow */}
          <span
            aria-hidden="true"
            className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-gray-900 dark:border-t-gray-800"
          />
        </span>
      )}
    </span>
  );
}
