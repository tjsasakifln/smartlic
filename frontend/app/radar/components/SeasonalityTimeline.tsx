"use client";

import React, { useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface TimelinePoint {
  mes: string;
  volume: number;
  quantidade: number;
  confianca?: number;
}

export interface TimelineSeries {
  name: string;
  data: TimelinePoint[];
  color: string;
}

export interface SeasonalityTimelineProps {
  series: TimelineSeries[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  height?: number;
  showLegend?: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(val: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(val);
}

function formatNumber(val: number): string {
  return new Intl.NumberFormat("pt-BR").format(val);
}

// ---------------------------------------------------------------------------
// Custom Tooltip
// ---------------------------------------------------------------------------

const TimelineTooltip = React.memo(function TimelineTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div
      className="bg-[var(--surface-elevated)] border border-[var(--border)] rounded-lg shadow-xl p-3 text-sm"
      data-testid="timeline-tooltip"
    >
      <p className="font-semibold text-[var(--ink)] mb-2">{label}</p>
      <div className="space-y-1">
        {payload.map((entry, i) => (
          <p key={i} className="flex items-center gap-2 text-xs" style={{ color: entry.color }}>
            <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ backgroundColor: entry.color }} />
            <span className="text-[var(--ink-secondary)]">{entry.name}:</span>
            <span className="font-medium text-[var(--ink)]">{formatCurrency(entry.value)}</span>
          </p>
        ))}
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function TimelineSkeleton({ height }: { height: number }) {
  return (
    <div className="animate-pulse" data-testid="timeline-skeleton">
      <div
        className="bg-[var(--surface-1)] rounded-xl w-full"
        style={{ height }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function TimelineEmpty() {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center"
      data-testid="timeline-empty"
    >
      <div className="w-12 h-12 rounded-full bg-[var(--surface-1)] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-[var(--ink-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
      </div>
      <p className="text-[var(--ink-secondary)] font-medium">Nenhum dado de tendencia disponivel</p>
      <p className="text-sm text-[var(--ink-muted)] mt-1">
        Selecione filtros para visualizar a sazonalidade ao longo do ano
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error State
// ---------------------------------------------------------------------------

function TimelineError({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center bg-[var(--surface-1)] rounded-xl"
      data-testid="timeline-error"
    >
      <div className="w-12 h-12 rounded-full bg-[var(--error-bg)] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-[var(--error)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      </div>
      <p className="text-[var(--error)] font-medium">Erro ao carregar timeline sazonal</p>
      <button
        onClick={onRetry}
        className="mt-3 px-4 py-2 text-sm font-medium text-[var(--brand-blue)] hover:bg-[var(--surface-2)] rounded-lg transition-colors"
      >
        Tentar novamente
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function SeasonalityTimeline({
  series,
  loading = false,
  error = null,
  onRetry,
  height = 300,
  showLegend = true,
}: SeasonalityTimelineProps) {
  const [isMobile, setIsMobile] = useState(false);

  React.useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  if (loading) return <TimelineSkeleton height={height} />;
  if (error) return <TimelineError onRetry={onRetry || (() => {})} />;
  if (!series || series.length === 0 || series.every((s) => s.data.length === 0)) {
    return <TimelineEmpty />;
  }

  // Merge data points from all series into a single chart-friendly format
  const chartData = useMemo(() => {
    if (!series.length) return [];

    const allLabels = new Set<string>();
    series.forEach((s) => s.data.forEach((d) => allLabels.add(d.mes)));
    const sortedLabels = Array.from(allLabels).sort();

    return sortedLabels.map((label) => {
      const point: Record<string, string | number> = { mes: label };
      series.forEach((s) => {
        const dp = s.data.find((d) => d.mes === label);
        if (dp) {
          point[s.name] = dp.volume;
        }
      });
      return point;
    });
  }, [series]);

  const chartHeight = isMobile ? Math.min(height, 220) : height;

  return (
    <div data-testid="seasonality-timeline">
      <ResponsiveContainer width="100%" height={chartHeight}>
        <LineChart data={chartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis
            dataKey="mes"
            tick={{ fill: "var(--ink-muted)", fontSize: isMobile ? 10 : 12 }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "var(--ink-muted)", fontSize: isMobile ? 10 : 12 }}
            axisLine={{ stroke: "var(--border)" }}
            tickLine={false}
            tickFormatter={(v: number) => {
              if (v >= 1000000) return `${(v / 1000000).toFixed(1)}M`;
              if (v >= 1000) return `${(v / 1000).toFixed(0)}k`;
              return String(v);
            }}
          />
          <Tooltip content={<TimelineTooltip />} />
          {showLegend && (
            <Legend
              wrapperStyle={{ fontSize: "12px", color: "var(--ink-muted)" }}
            />
          )}

          {series.map((s) => (
            <Line
              key={s.name}
              type="monotone"
              dataKey={s.name}
              name={s.name}
              stroke={s.color}
              strokeWidth={2}
              dot={{ r: 3, strokeWidth: 1, fill: "var(--surface-0)" }}
              activeDot={{ r: 5, strokeWidth: 2 }}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
