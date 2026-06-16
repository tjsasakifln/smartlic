"use client";

import { useState, useEffect, useCallback } from "react";
import { useAuth } from "../../components/AuthProvider";
import Link from "next/link";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MrrHistoryEntry {
  month: string;
  mrr: number;
  subscriber_count: number;
}

interface RevenueMetrics {
  mrr: number;
  churn_rate_30d: number;
  trial_to_paid_30d: number;
  trial_to_paid_90d: number;
  activation_d7: number;
  retention_d1: number;
  retention_d7: number;
  retention_d30: number;
  arpa: number;
  total_subscribers: number;
  period_start: string;
  period_end: string;
  mrr_history: MrrHistoryEntry[];
}

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function formatBRL(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
    .format(value)
    .replace(/ /g, " ");
}

function formatPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function formatInt(value: number): string {
  return new Intl.NumberFormat("pt-BR").format(value);
}

function formatMonth(month: string): string {
  if (!month || month.length < 7) return month;
  const [y, m] = month.split("-");
  const meses: Record<string, string> = {
    "01": "jan", "02": "fev", "03": "mar", "04": "abr",
    "05": "mai", "06": "jun", "07": "jul", "08": "ago",
    "09": "set", "10": "out", "11": "nov", "12": "dez",
  };
  return `${meses[m] || m}/${y.slice(2)}`;
}

// ---------------------------------------------------------------------------
// Tooltip for MRR chart
// ---------------------------------------------------------------------------

interface TooltipPayloadEntry {
  name: string;
  value: number;
  color: string;
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-[var(--surface-elevated)] border border-[var(--border)] rounded-card p-3 shadow-lg text-sm">
      <p className="font-medium text-[var(--ink)] mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color }} className="text-xs">
          {entry.name}: {formatBRL(entry.value)}
        </p>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Metric Card
// ---------------------------------------------------------------------------

interface MetricCardProps {
  label: string;
  value: string;
  sublabel?: string;
  accent?: "positive" | "negative" | "neutral";
}

function MetricCard({ label, value, sublabel, accent }: MetricCardProps) {
  const valueColor =
    accent === "positive"
      ? "text-green-600 dark:text-green-400"
      : accent === "negative"
        ? "text-[var(--error)]"
        : "text-[var(--ink)]";

  return (
    <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-card p-5 flex flex-col gap-1">
      <div className="text-sm text-[var(--ink-secondary)]">{label}</div>
      <div className={`text-2xl font-bold font-data ${valueColor}`}>{value}</div>
      {sublabel && (
        <div className="text-xs text-[var(--ink-secondary)]">{sublabel}</div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function AdminFounderMetricsPage() {
  const { session, loading: authLoading, isAdmin, isAdminLoading } = useAuth();
  const [data, setData] = useState<RevenueMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchMetrics = useCallback(async () => {
    if (!session?.access_token) return;
    setLoading(true);
    setError(null);
    try {
      // Goes through the catch-all admin proxy at /api/admin/[...path]/route.ts
      const res = await fetch("/api/admin/metrics/revenue", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.status === 401) {
        setError("Autenticacao necessaria.");
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || `Erro ${res.status}`);
      }
      const json = await res.json();
      setData(json);
      setLastRefresh(new Date());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erro ao carregar metricas financeiras"
      );
    } finally {
      setLoading(false);
    }
  }, [session?.access_token]);

  useEffect(() => {
    if (session?.access_token && isAdmin) {
      fetchMetrics();
    } else if (!authLoading && !isAdminLoading) {
      setLoading(false);
    }
  }, [session?.access_token, isAdmin, isAdminLoading, authLoading, fetchMetrics]);

  // ----- Auth guards (same pattern as existing admin pages) -----

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--canvas)]">
        <p className="text-[var(--ink-secondary)]">Carregando...</p>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--canvas)]">
        <Link href="/login" className="text-[var(--brand-blue)]">
          Login necessario
        </Link>
      </div>
    );
  }

  if (!isAdmin && !loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--canvas)]">
        <div className="text-center max-w-md px-4">
          <div className="w-16 h-16 mx-auto mb-6 rounded-full bg-[var(--error-subtle)] flex items-center justify-center">
            <svg
              role="img"
              aria-label="Aviso"
              className="w-8 h-8 text-[var(--error)]"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h1 className="text-2xl font-display font-bold text-[var(--ink)] mb-2">
            Acesso Restrito
          </h1>
          <p className="text-[var(--ink-secondary)] mb-6">
            Esta pagina e exclusiva para administradores.
          </p>
          <Link
            href="/buscar"
            className="inline-block px-6 py-2 bg-[var(--brand-navy)] text-white rounded-button hover:bg-[var(--brand-blue)] transition-colors"
          >
            Voltar
          </Link>
        </div>
      </div>
    );
  }

  const d = data;
  const chartData =
    d?.mrr_history?.map((h) => ({
      month: formatMonth(h.month),
      mrr: h.mrr,
      assinantes: h.subscriber_count,
    })) ?? [];

  return (
    <div className="min-h-screen bg-[var(--canvas)] py-8 px-4">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-display font-bold text-[var(--ink)]">
              Metricas Financeiras
            </h1>
            <p className="text-[var(--ink-secondary)]">
              {d
                ? `Periodo: ${d.period_start} a ${d.period_end}`
                : "Carregando..."}
              {lastRefresh && (
                <span className="ml-2 text-xs">
                  (atualizado {lastRefresh.toLocaleTimeString("pt-BR")})
                </span>
              )}
            </p>
          </div>
          <div className="flex gap-3">
            <Link
              href="/admin"
              className="px-4 py-2 border border-[var(--border)] rounded-button text-sm hover:bg-[var(--surface-1)] text-[var(--ink-secondary)]"
            >
              Usuarios
            </Link>
            <Link
              href="/admin/cache"
              className="px-4 py-2 border border-[var(--border)] rounded-button text-sm hover:bg-[var(--surface-1)] text-[var(--ink-secondary)]"
            >
              Cache
            </Link>
            <Link
              href="/admin/slo"
              className="px-4 py-2 border border-[var(--border)] rounded-button text-sm hover:bg-[var(--surface-1)] text-[var(--ink-secondary)]"
            >
              SLOs
            </Link>
            <button
              onClick={fetchMetrics}
              disabled={loading}
              className="px-4 py-2 bg-[var(--brand-navy)] text-white rounded-button text-sm hover:bg-[var(--brand-blue)] disabled:opacity-50"
            >
              {loading ? "Atualizando..." : "Atualizar"}
            </button>
          </div>
        </div>

        {/* Error state */}
        {error && (
          <div className="mb-6 p-4 bg-[var(--error-subtle)] border border-[var(--error)] rounded-card text-[var(--error)] flex items-center justify-between">
            <span>{error}</span>
            <button
              onClick={fetchMetrics}
              className="ml-4 px-3 py-1 text-sm border border-[var(--error)] rounded-button hover:bg-[var(--error-subtle)]"
            >
              Tentar novamente
            </button>
          </div>
        )}

        {/* Loading skeleton */}
        {loading && !d && (
          <div>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
              {Array.from({ length: 5 }).map((_, i) => (
                <div
                  key={i}
                  className="bg-[var(--surface-1)] border border-[var(--border)] rounded-card p-5 animate-pulse"
                >
                  <div className="h-3 w-20 bg-[var(--surface-2)] rounded mb-3" />
                  <div className="h-7 w-28 bg-[var(--surface-2)] rounded" />
                </div>
              ))}
            </div>
            <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-card p-6 animate-pulse">
              <div className="h-4 w-40 bg-[var(--surface-2)] rounded mb-4" />
              <div className="h-64 bg-[var(--surface-2)] rounded" />
            </div>
          </div>
        )}

        {/* Metrics content */}
        {d && (
          <>
            {/* Primary metric cards */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4 mb-8">
              <MetricCard
                label="MRR"
                value={formatBRL(d.mrr)}
                sublabel="Receita recorrente mensal"
                accent={d.mrr > 0 ? "positive" : "neutral"}
              />
              <MetricCard
                label="Churn (30d)"
                value={formatPct(d.churn_rate_30d)}
                sublabel="Taxa de cancelamento"
                accent={
                  d.churn_rate_30d > 0.1
                    ? "negative"
                    : d.churn_rate_30d > 0.05
                      ? "neutral"
                      : "positive"
                }
              />
              <MetricCard
                label="Trial → Paid (30d)"
                value={formatPct(d.trial_to_paid_30d)}
                sublabel="Conversao trial"
                accent={
                  d.trial_to_paid_30d > 0.15
                    ? "positive"
                    : d.trial_to_paid_30d > 0.08
                      ? "neutral"
                      : "negative"
                }
              />
              <MetricCard
                label="ARPA"
                value={formatBRL(d.arpa)}
                sublabel="Receita media por assinante"
                accent={d.arpa > 0 ? "positive" : "neutral"}
              />
              <MetricCard
                label="Assinantes"
                value={formatInt(d.total_subscribers)}
                sublabel="Total de assinantes ativos"
                accent={d.total_subscribers > 0 ? "positive" : "neutral"}
              />
            </div>

            {/* MRR History Line Chart */}
            <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-card p-6 mb-8">
              <h2 className="text-lg font-semibold text-[var(--ink)] mb-1">
                Evolucao do MRR
              </h2>
              <p className="text-sm text-[var(--ink-secondary)] mb-4">
                Receita recorrente mensal ao longo do tempo
              </p>

              {chartData.length === 0 ? (
                <div className="h-64 flex items-center justify-center text-[var(--ink-secondary)] text-sm">
                  Dados de MRR historico indisponiveis
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={chartData}>
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="var(--border)"
                    />
                    <XAxis
                      dataKey="month"
                      tick={{ fill: "var(--ink-muted)", fontSize: 12 }}
                      axisLine={{ stroke: "var(--border)" }}
                    />
                    <YAxis
                      tick={{ fill: "var(--ink-muted)", fontSize: 12 }}
                      axisLine={{ stroke: "var(--border)" }}
                      tickFormatter={(v: number) =>
                        v >= 1000
                          ? `R$ ${(v / 1000).toFixed(0)}k`
                          : `R$${v}`
                      }
                      width={80}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="mrr"
                      stroke="var(--brand-blue)"
                      strokeWidth={2}
                      dot={{ fill: "var(--brand-blue)", r: 4 }}
                      activeDot={{ r: 6 }}
                      name="MRR"
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>

            {/* Engagement metrics */}
            <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-card p-6">
              <h2 className="text-lg font-semibold text-[var(--ink)] mb-3">
                Metricas de Engajamento
              </h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="flex flex-col gap-1">
                  <span className="text-sm text-[var(--ink-secondary)]">
                    Retencao D30
                  </span>
                  <span className="text-xl font-bold font-data text-[var(--ink)]">
                    {formatPct(d.retention_d30)}
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-sm text-[var(--ink-secondary)]">
                    Ativacao D7
                  </span>
                  <span className="text-xl font-bold font-data text-[var(--ink)]">
                    {formatPct(d.activation_d7)}
                  </span>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-sm text-[var(--ink-secondary)]">
                    Trial → Paid (90d)
                  </span>
                  <span className="text-xl font-bold font-data text-[var(--ink)]">
                    {formatPct(d.trial_to_paid_90d)}
                  </span>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Empty state when not loading, no data, and no error */}
        {!loading && !d && !error && (
          <div className="flex flex-col items-center justify-center py-20 text-[var(--ink-secondary)]">
            <svg
              className="w-12 h-12 mb-4 opacity-40"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"
              />
            </svg>
            <p>Nenhum dado disponivel no momento.</p>
            <button
              onClick={fetchMetrics}
              className="mt-4 px-4 py-2 bg-[var(--brand-navy)] text-white rounded-button text-sm hover:bg-[var(--brand-blue)]"
            >
              Carregar metricas
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
