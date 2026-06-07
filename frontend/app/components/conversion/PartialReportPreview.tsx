"use client";

/**
 * CONV-003-4 (#1515): PartialReportPreview
 *
 * Embeddable lead magnet that shows 3-5 real sector opportunities with
 * obscured values, then prompts the visitor to submit their email to
 * unlock the full report.
 *
 * Data source: GET /v1/sectors/{slug}/stats (public, no auth).
 * Stats include sample_items from the DataLake for the given sector.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { LeadCaptureIntermediate } from "./LeadCaptureIntermediate";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SampleItem {
  titulo: string;
  orgao: string;
  valor: number | null;
  uf: string;
  data: string;
}

interface SectorStatsResponse {
  sector_id: string;
  sector_name: string;
  sample_items: SampleItem[];
  total_open: number;
  total_value: number;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface PartialReportPreviewProps {
  /** Sector ID in underscore format (e.g. "ti_software", "engenharia") */
  sectorId: string;
  /** Source page URL for tracking */
  sourcePage: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Convert sector_id to slug: "ti_software" → "ti-software" */
function sectorIdToSlug(sectorId: string): string {
  return sectorId.replace(/_/g, "-");
}

/**
 * Obscure a monetary value as "R$ XXX.XXX".
 * Shows only a broad magnitude (rounded to nearest 100k), not the exact value.
 * This prevents the visitor from seeing precise bid amounts without
 * submitting their email.
 */
function obscureValue(valor: number | null): string {
  if (valor === null || valor <= 0) return "R$ XXX.XXX";
  // Round to nearest 100k to obscure the exact value
  const rounded = Math.round(valor / 100000) * 100;
  if (rounded <= 0) return "R$ XXX.XXX";
  return `R$ ${rounded}.000`;
}

/**
 * Obscure a date as "MM/AAAA".
 * Only shows month and year, not the full date.
 */
function obscureDate(dataStr: string): string {
  if (!dataStr || dataStr.length < 7) return "MM/AAAA";
  // dataStr may be "2026-05-15" or "2026-05-15T..."
  const parts = dataStr.split("T")[0].split("-");
  if (parts.length < 2) return "MM/AAAA";
  return `${parts[1]}/${parts[0]}`;
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function BuildingIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
      />
    </svg>
  );
}

function LockClosedIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PartialReportPreview({
  sectorId,
  sourcePage,
}: PartialReportPreviewProps) {
  const [items, setItems] = useState<SampleItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [emailCaptured, setEmailCaptured] = useState(false);
  const mountedRef = useRef(true);

  const slug = sectorIdToSlug(sectorId);

  // Track mixpanel event
  const trackEvent = useCallback(
    (event: string, extra?: Record<string, unknown>) => {
      if (typeof window !== "undefined" && (window as unknown as { mixpanel?: { track: (name: string, data: unknown) => void } }).mixpanel) {
        (window as unknown as { mixpanel: { track: (name: string, data: unknown) => void } }).mixpanel.track(event, {
          sector_id: sectorId,
          slug,
          source_page: sourcePage,
          ...extra,
        });
      }
    },
    [sectorId, slug, sourcePage],
  );

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);

      trackEvent("partial_preview_viewed");

      try {
        const response = await fetch(`/api/sectors/${slug}/stats`);
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const data: SectorStatsResponse = await response.json();

        if (cancelled) return;

        if (data.sample_items && data.sample_items.length > 0) {
          // Show up to 5 items
          setItems(data.sample_items.slice(0, 5));
        } else {
          // No data — show fallback message
          setError("Nenhuma oportunidade encontrada para este setor no momento.");
        }
      } catch (err) {
        if (cancelled) return;
        setError(
          "Não foi possível carregar as oportunidades no momento. Tente novamente mais tarde.",
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchData();

    return () => {
      cancelled = true;
      mountedRef.current = false;
    };
  }, [slug, trackEvent]);

  const handleSuccess = useCallback(() => {
    setEmailCaptured(true);
    trackEvent("partial_preview_email_captured");
  }, [trackEvent]);

  // -----------------------------------------------------------------------
  // Loading skeleton
  // -----------------------------------------------------------------------

  if (loading) {
    return (
      <section
        aria-label="Pré-visualização de oportunidades"
        className="my-8 rounded-card border border-strong bg-surface-0 shadow-sm overflow-hidden"
        data-testid="partial-preview"
      >
        <div className="bg-brand-navy px-6 py-5">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <BuildingIcon className="w-5 h-5" />
            Oportunidades recentes do setor
          </h2>
        </div>
        <div className="p-6 space-y-4" data-testid="partial-preview-loading">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="animate-pulse border border-strong rounded-card p-4 space-y-3"
              data-testid={`partial-preview-skeleton-${i}`}
            >
              <div className="h-4 w-1/3 bg-surface-2 rounded" />
              <div className="h-4 w-2/3 bg-surface-2 rounded" />
              <div className="h-4 w-1/4 bg-surface-2 rounded" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  // -----------------------------------------------------------------------
  // Error state
  // -----------------------------------------------------------------------

  if (error && items.length === 0) {
    return (
      <section
        aria-label="Pré-visualização de oportunidades"
        className="my-8 rounded-card border border-strong bg-surface-0 shadow-sm overflow-hidden"
        data-testid="partial-preview"
      >
        <div className="bg-brand-navy px-6 py-5">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <BuildingIcon className="w-5 h-5" />
            Oportunidades recentes do setor
          </h2>
        </div>
        <div className="p-6">
          <div
            className="text-center py-8 text-ink-secondary"
            data-testid="partial-preview-error"
          >
            <p>{error}</p>
          </div>
        </div>
      </section>
    );
  }

  // -----------------------------------------------------------------------
  // Success (email already captured)
  // -----------------------------------------------------------------------

  if (emailCaptured) {
    return (
      <section
        aria-label="Relatório desbloqueado"
        className="my-8 rounded-card border border-strong bg-surface-0 shadow-sm overflow-hidden"
        data-testid="partial-preview"
      >
        <div className="bg-brand-navy px-6 py-5">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <BuildingIcon className="w-5 h-5" />
            Relatório desbloqueado!
          </h2>
        </div>
        <div className="p-6 text-center" data-testid="partial-preview-success">
          <div className="text-4xl mb-4">&#x2705;</div>
          <p className="text-lg font-semibold text-ink mb-2">
            Seu relatório está pronto!
          </p>
          <p className="text-sm text-ink-secondary mb-6">
            Enviamos um link no seu email para acessar o relatório completo com
            todas as oportunidades, valores detalhados e análise de viabilidade.
          </p>
        </div>
      </section>
    );
  }

  // -----------------------------------------------------------------------
  // Main — cards with obscured data + email CTA
  // -----------------------------------------------------------------------

  return (
    <section
      aria-label="Pré-visualização de oportunidades"
      className="my-8 rounded-card border border-strong bg-surface-0 shadow-sm overflow-hidden"
      data-testid="partial-preview"
    >
      {/* Header */}
      <div className="bg-brand-navy px-6 py-5">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <BuildingIcon className="w-5 h-5" />
          Oportunidades recentes do setor
        </h2>
        <p className="text-sm text-white/80 mt-1">
          Pré-visualização com dados reais dos últimos 30 dias
        </p>
      </div>

      {/* Cards */}
      <div className="p-6 space-y-4">
        <div className="space-y-3">
          {items.map((item, index) => (
            <div
              key={index}
              className="border border-strong rounded-card p-4"
              data-testid={`partial-preview-card-${index}`}
            >
              <div className="flex flex-col gap-1">
                {/* Orgão (visible) */}
                <p className="text-sm font-semibold text-ink truncate">
                  {item.orgao}
                </p>
                {/* Objeto (visible, truncated) */}
                <p className="text-sm text-ink-secondary line-clamp-2">
                  {item.titulo}
                </p>
                {/* Obscured value + date */}
                <div className="flex items-center gap-4 mt-2">
                  <span
                    className="inline-flex items-center gap-1 text-sm font-mono text-ink-muted"
                    data-testid={`partial-preview-obscured-value-${index}`}
                  >
                    <LockClosedIcon className="w-3.5 h-3.5" />
                    {obscureValue(item.valor)}
                  </span>
                  <span
                    className="inline-flex items-center gap-1 text-sm text-ink-muted"
                    data-testid={`partial-preview-obscured-date-${index}`}
                  >
                    <LockClosedIcon className="w-3.5 h-3.5" />
                    {obscureDate(item.data)}
                  </span>
                  <span className="text-xs text-ink-muted ml-auto">
                    {item.uf}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Email CTA */}
        <div className="border-t border-strong pt-6 mt-6">
          <p className="text-sm font-semibold text-ink text-center mb-4">
            Digite seu email para ver o relatório completo
          </p>
          <LeadCaptureIntermediate
            sectorId={sectorId}
            sourcePage={sourcePage}
            onSuccess={handleSuccess}
          />
        </div>
      </div>
    </section>
  );
}

export default PartialReportPreview;
