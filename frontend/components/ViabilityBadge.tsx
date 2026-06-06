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

/** Factor label for tooltip display */
function factorLine(name: string, score: number, label: string): string {
  return `${name}: ${label} (${score}/100)`;
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

  // Build tooltip lines
  const tooltipLines: string[] = [`Viabilidade: ${score ?? "?"}/100`];
  if (factors) {
    tooltipLines.push(
      factorLine("Modalidade", factors.modalidade, factors.modalidade_label),
      factorLine("Prazo", factors.timeline, factors.timeline_label),
      factorLine("Valor", factors.value_fit, factors.value_fit_label),
      factorLine("UF", factors.geography, factors.geography_label),
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
 */
function ViabilityTooltip({
  children,
  tooltipLines,
  ariaLabel,
  bg,
  level,
  score,
  bidId,
}: {
  children: React.ReactNode;
  tooltipLines: string[];
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
            "w-max max-w-[240px]",
            "bg-gray-900 dark:bg-gray-800 text-white text-[10px] leading-relaxed",
            "rounded-md px-2.5 py-2 shadow-lg",
            "pointer-events-none",
          ].join(" ")}
        >
          {tooltipLines.map((line, i) => (
            <p key={i} className={i === 0 ? "font-semibold mb-1" : "text-gray-300"}>
              {line}
            </p>
          ))}
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
