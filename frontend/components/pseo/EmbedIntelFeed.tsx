"use client";
/**
 * EmbedIntelFeed — Issue #1519 (NETINT-014)
 *
 * Compact market intelligence feed widget for SEO programmatic pages.
 * Shows "O mercado está aquecendo em [setor]" with 3 relevant signals.
 *
 * - Lazy-load via IntersectionObserver (only fetches when visible)
 * - ISR-safe: static fallback if API fails (no build break)
 * - Height: ~300px, horizontal scroll on mobile (<640px)
 * - Vertical stack on desktop
 *
 * Usage:
 *   <EmbedIntelFeed sector="engenharia" uf="SP" />
 */
import { useEffect, useRef, useState } from "react";

export interface EmbedIntelFeedProps {
  /** Nome do setor em formato slug (ex: "engenharia") */
  sector: string;
  /** UF opcional (ex: "SP") */
  uf?: string;
}

interface SignalData {
  label: string;
  value: string;
  trend?: string | null;
}

interface IntelFeedData {
  sector: string;
  signals: SignalData[];
  generated_at: string;
}

// ---------------------------------------------------------------------------
// Static fallback — ISR-safe, usado quando API offline
// ---------------------------------------------------------------------------

function staticFallback(sectorLabel: string): IntelFeedData {
  const name = sectorLabel.charAt(0).toUpperCase() + sectorLabel.slice(1);
  return {
    sector: name,
    signals: [
      { label: "Acompanhe as oportunidades", value: name, trend: null },
      { label: "Mercado em análise", value: "Aguardando dados", trend: null },
      { label: "Dados em consolidação", value: "Contratos deste mês", trend: null },
    ],
    generated_at: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Trend icon
// ---------------------------------------------------------------------------

function TrendIcon({ trend }: { trend?: string | null }) {
  if (trend === "up") {
    return (
      <svg
        className="w-4 h-4 text-green-500 shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
      </svg>
    );
  }
  if (trend === "down") {
    return (
      <svg
        className="w-4 h-4 text-red-500 shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth="2"
      >
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
      </svg>
    );
  }
  // stable or null — render subtle dash
  return (
    <svg
      className="w-4 h-4 text-[var(--ink-muted)] shrink-0"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="2"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function IntelFeedSkeleton() {
  return (
    <div
      className="rounded-xl border border-[var(--border)] bg-[var(--surface-0)] p-5 animate-pulse"
      style={{ minHeight: "280px" }}
      aria-label="Carregando inteligência de mercado"
    >
      <div className="h-5 bg-[var(--surface-2)] rounded w-56 mb-5" />
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="flex items-start gap-3">
            <div className="w-4 h-4 bg-[var(--surface-2)] rounded shrink-0 mt-0.5" />
            <div className="flex-1 space-y-1">
              <div className="h-4 bg-[var(--surface-2)] rounded w-3/4" />
              <div className="h-3 bg-[var(--surface-2)] rounded w-1/2" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function EmbedIntelFeed({ sector, uf }: EmbedIntelFeedProps) {
  const [data, setData] = useState<IntelFeedData | null>(null);
  const [loading, setLoading] = useState(true);
  const observerRef = useRef<HTMLDivElement | null>(null);
  const fetchedRef = useRef(false);

  useEffect(() => {
    const el = observerRef.current;
    if (!el) return;

    const handleIntersection = (entries: IntersectionObserverEntry[]) => {
      const entry = entries[0];
      if (!entry.isIntersecting) return;
      if (fetchedRef.current) return;
      fetchedRef.current = true;

      // Lazy-load data when visible
      setLoading(true);

      const params = new URLSearchParams({ sector });
      if (uf) params.set("uf", uf);

      fetch(`/api/pseo/intel-feed?${params.toString()}`)
        .then((res) => {
          if (!res.ok) throw new Error("API error");
          return res.json();
        })
        .then((json: IntelFeedData) => {
          setData(json);
          setLoading(false);
        })
        .catch(() => {
          // ISR-safe: serve fallback estático
          setData(staticFallback(sector));
          setLoading(false);
        });
    };

    const observer = new IntersectionObserver(handleIntersection, {
      rootMargin: "200px",
    });

    observer.observe(el);

    return () => {
      observer.disconnect();
    };
  }, [sector, uf]);

  const sectorDisplay =
    data?.sector ||
    sector.charAt(0).toUpperCase() + sector.slice(1);

  return (
    <section
      ref={observerRef}
      className="w-full"
      data-embed-intel-feed
      aria-label="Inteligência de Mercado"
    >
      {loading && !data ? (
        <IntelFeedSkeleton />
      ) : (
        <div
          className="rounded-xl border border-[var(--border)] bg-[var(--surface-0)] p-5"
          style={{ minHeight: "280px" }}
        >
          {/* Header */}
          <h3 className="text-base font-semibold text-[var(--ink)] mb-1">
            Mercado de {sectorDisplay}
          </h3>
          <p className="text-xs text-[var(--ink-secondary)] mb-4">
            Inteligência agregada em tempo real
          </p>

          {/* Signals: horizontal scroll on mobile, vertical stack on desktop */}
          <div className="flex gap-3 overflow-x-auto pb-2 sm:flex-col sm:overflow-x-visible scrollbar-thin">
            {(data?.signals ?? []).length === 0 ? (
              <p className="text-sm text-[var(--ink-muted)]">
                Dados de mercado em consolidação.
              </p>
            ) : (
              (data?.signals ?? []).map((signal, idx) => (
                <div
                  key={idx}
                  className="flex items-start gap-3 min-w-[220px] sm:min-w-0 p-3 rounded-lg bg-[var(--surface-1)] sm:bg-transparent sm:p-0 shrink-0"
                >
                  <TrendIcon trend={signal.trend} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-[var(--ink)] leading-snug">
                      {signal.label}
                    </p>
                    <p className="text-xs text-[var(--ink-secondary)] mt-0.5">
                      {signal.value}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Footer */}
          {data?.generated_at && (
            <p className="text-[10px] text-[var(--ink-muted)] mt-3 text-right">
              Dados:{" "}
              {new Date(data.generated_at).toLocaleDateString("pt-BR", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </p>
          )}
        </div>
      )}
    </section>
  );
}
