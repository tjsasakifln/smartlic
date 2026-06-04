"use client";

import { useEffect } from "react";

// ---------------------------------------------------------------------------
// LIFECYCLE-003 (#1428) / LIFECYCLE-004 (#1429): Lifecycle data types
// ---------------------------------------------------------------------------

interface PowerUser {
  user_id: string;
  email: string;
  full_name: string | null;
  company: string | null;
  logins_14d: number;
  pipeline_count: number;
  alert_count: number;
}

interface LifecycleTransition {
  user_id: string;
  previous_lifecycle: string | null;
  new_lifecycle: string;
  changed_at: string;
}

interface SegmentsData {
  count_by_state: Record<string, number>;
  total_users: number;
  transitions_last_week: LifecycleTransition[];
  power_users: PowerUser[];
  queried_at?: string;
}

interface LifecycleWidgetProps {
  /** Segments data from the backend, or null while loading / on error. */
  data: SegmentsData | null;
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
}

// ---------------------------------------------------------------------------
// Lifecycle state metadata: all 10 states defined in the DB enum
// user_lifecycle_state (migration 20260604170000_user_lifecycle.sql)
// ---------------------------------------------------------------------------

interface StateMeta {
  key: string;
  label: string;
  bg: string;
  text: string;
  border: string;
}

const LIFECYCLE_STATES: StateMeta[] = [
  { key: "anonymous",      label: "Anonimo",       bg: "bg-gray-50 dark:bg-gray-950/30",   text: "text-gray-600",    border: "border-gray-200 dark:border-gray-700" },
  { key: "lead",           label: "Lead",           bg: "bg-indigo-50 dark:bg-indigo-950/30",text: "text-indigo-600",  border: "border-indigo-200 dark:border-indigo-800" },
  { key: "trial_active",   label: "Trial Ativo",    bg: "bg-blue-50 dark:bg-blue-950/30",   text: "text-blue-600",    border: "border-blue-200 dark:border-blue-800" },
  { key: "trial_limited",  label: "Trial Limitado", bg: "bg-amber-50 dark:bg-amber-950/30",  text: "text-amber-600",  border: "border-amber-200 dark:border-amber-800" },
  { key: "trial_expired",  label: "Trial Expirado", bg: "bg-orange-50 dark:bg-orange-950/30",text: "text-orange-600", border: "border-orange-200 dark:border-orange-800" },
  { key: "paid_active",    label: "Ativo (Pago)",   bg: "bg-green-50 dark:bg-green-950/30",  text: "text-green-600",  border: "border-green-200 dark:border-green-800" },
  { key: "paid_past_due",  label: "Pag. Pendente",  bg: "bg-red-50 dark:bg-red-950/30",     text: "text-red-600",    border: "border-red-200 dark:border-red-800" },
  { key: "canceled",       label: "Cancelado",      bg: "bg-gray-100 dark:bg-gray-800",      text: "text-gray-600",   border: "border-gray-200 dark:border-gray-700" },
  { key: "churned",        label: "Churned",        bg: "bg-gray-200 dark:bg-gray-700",      text: "text-gray-700",   border: "border-gray-300 dark:border-gray-600" },
  { key: "power_user",     label: "Power User",     bg: "bg-violet-50 dark:bg-violet-950/30",text: "text-violet-600", border: "border-violet-200 dark:border-violet-800" },
];

/** Ordered list so cards render in a logical sequence. */
const STATE_ORDER = LIFECYCLE_STATES.map((s) => s.key);

function stateMeta(key: string): StateMeta {
  return LIFECYCLE_STATES.find((s) => s.key === key) ?? {
    key,
    label: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    bg: "bg-gray-50 dark:bg-gray-950/30",
    text: "text-gray-600",
    border: "border-gray-200 dark:border-gray-700",
  };
}

function lifecycleLabel(key: string): string {
  return stateMeta(key).label;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function LifecycleWidget({ data, loading, error, onRetry }: LifecycleWidgetProps) {
  // Mixpanel: track lifecycle_state_changed on successful load
  useEffect(() => {
    if (!loading && data && data.total_users > 0) {
      const mp = (window as unknown as { mixpanel?: { track: (e: string, p?: Record<string, unknown>) => void } }).mixpanel;
      if (mp) {
        mp.track("lifecycle_state_changed", {
          total_users: data.total_users,
          states: Object.keys(data.count_by_state).length,
          transitions: data.transitions_last_week.length,
          power_users: data.power_users.length,
        });
      }
    }
  }, [loading, data]);

  // --- Loading skeleton ---
  if (loading) {
    return (
      <div className="mb-8 bg-[var(--surface-0)] border border-[var(--border)] rounded-card p-6 animate-pulse">
        <div className="h-6 w-56 bg-gray-200 dark:bg-gray-700 rounded mb-4" />
        <div className="grid grid-cols-5 gap-3 mb-6">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-20 bg-gray-100 dark:bg-gray-800 rounded" />
          ))}
        </div>
        <div className="h-32 bg-gray-100 dark:bg-gray-800 rounded" />
      </div>
    );
  }

  // --- Error state ---
  if (error) {
    return (
      <div className="mb-8 bg-[var(--surface-0)] border border-[var(--border)] rounded-card p-6">
        <h2 className="text-lg font-semibold text-[var(--ink)] mb-4">
          Ciclo de Vida dos Usuarios
        </h2>
        <div className="text-center py-6">
          <p className="text-sm text-[var(--error)] mb-3">
            Erro ao carregar dados de ciclo de vida: {error}
          </p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="text-xs px-3 py-1 border border-[var(--border)] rounded-button hover:bg-[var(--surface-1)] text-[var(--ink-secondary)]"
            >
              Tentar novamente
            </button>
          )}
        </div>
      </div>
    );
  }

  // --- Empty / no data ---
  if (!data || data.total_users === 0) {
    return (
      <div className="mb-8 bg-[var(--surface-0)] border border-[var(--border)] rounded-card p-6">
        <h2 className="text-lg font-semibold text-[var(--ink)] mb-4">
          Ciclo de Vida dos Usuarios
        </h2>
        <p className="text-sm text-[var(--ink-muted)]">
          Nenhum dado disponivel. Os dados de ciclo de vida serao exibidos apos o proximo calculo em lote.
        </p>
      </div>
    );
  }

  // --- Build per-state rows, sorted by STATE_ORDER ---
  const stateEntries = STATE_ORDER
    .filter((key) => (data.count_by_state[key] ?? 0) > 0)
    .map((key) => ({ key, count: data.count_by_state[key] ?? 0 }));

  // --- Transitions (sorted newest-first) ---
  const transitions = [...data.transitions_last_week].sort(
    (a, b) => new Date(b.changed_at).getTime() - new Date(a.changed_at).getTime(),
  );

  // --- Power users ---
  const powerUsers = data.power_users;

  return (
    <div className="mb-8 bg-[var(--surface-0)] border border-[var(--border)] rounded-card p-6">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-[var(--ink)]">
          Ciclo de Vida dos Usuarios
        </h2>
        <div className="text-xs text-[var(--ink-muted)]">
          {data.total_users} usuario{data.total_users !== 1 ? "s" : ""}
          {data.queried_at ? (
            <span className="ml-2">
              | {new Date(data.queried_at).toLocaleString("pt-BR")}
            </span>
          ) : null}
        </div>
      </div>

      {/* KPI Cards — one per lifecycle state */}
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 mb-6">
        {stateEntries.map(({ key, count }) => {
          const meta = stateMeta(key);
          return (
            <div
              key={key}
              className={`${meta.bg} ${meta.border} border rounded-card p-3 text-center`}
            >
              <p className={`text-2xl font-bold ${meta.text}`}>
                {count}
              </p>
              <p className="text-xs text-[var(--ink-secondary)] mt-1 truncate">
                {meta.label}
              </p>
            </div>
          );
        })}
      </div>

      {/* Two-column layout: transitions + power users */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* === Transition Table === */}
        <div>
          <h3 className="text-sm font-medium text-[var(--ink-secondary)] mb-2">
            Transicoes na Ultima Semana ({transitions.length})
          </h3>
          {transitions.length === 0 ? (
            <p className="text-xs text-[var(--ink-muted)]">
              Nenhuma transicao registrada na ultima semana.
            </p>
          ) : (
            <div className="overflow-x-auto max-h-64 overflow-y-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)]">
                    <th className="text-left py-2 pr-2 text-xs font-medium text-[var(--ink-secondary)]">Usuario</th>
                    <th className="text-left py-2 px-2 text-xs font-medium text-[var(--ink-secondary)]">De</th>
                    <th className="text-left py-2 px-2 text-xs font-medium text-[var(--ink-secondary)]">Para</th>
                    <th className="text-right py-2 pl-2 text-xs font-medium text-[var(--ink-secondary)]">Data</th>
                  </tr>
                </thead>
                <tbody>
                  {transitions.slice(0, 20).map((t, i) => (
                    <tr
                      key={`${t.user_id}-${t.changed_at}-${i}`}
                      className="border-b border-[var(--border)] hover:bg-[var(--surface-1)]"
                    >
                      <td className="py-2 pr-2 text-xs truncate max-w-[120px]" title={t.user_id}>
                        {t.user_id.slice(0, 8)}...
                      </td>
                      <td className="py-2 px-2 text-xs text-[var(--ink-secondary)]">
                        {t.previous_lifecycle ? lifecycleLabel(t.previous_lifecycle) : "-"}
                      </td>
                      <td className="py-2 px-2 text-xs font-medium">
                        {lifecycleLabel(t.new_lifecycle)}
                      </td>
                      <td className="py-2 pl-2 text-xs text-right text-[var(--ink-secondary)] whitespace-nowrap">
                        {new Date(t.changed_at).toLocaleDateString("pt-BR")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* === Power Users === */}
        <div>
          <h3 className="text-sm font-medium text-[var(--ink-secondary)] mb-2">
            Power Users ({powerUsers.length})
          </h3>
          {powerUsers.length === 0 ? (
            <p className="text-xs text-[var(--ink-muted)]">
              Nenhum power user identificado. Usuarios com &ge;5 logins/14d, &ge;3 pipeline items e &ge;1 alerta ativo sao classificados como power users.
            </p>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {powerUsers.map((pu) => (
                <div
                  key={pu.user_id}
                  className="flex items-center gap-3 p-3 rounded-card border border-[var(--border)] bg-[var(--surface-1)]"
                >
                  <div className="w-8 h-8 rounded-full bg-violet-100 dark:bg-violet-900/30 flex items-center justify-center flex-shrink-0">
                    <span className="text-xs font-bold text-violet-600 dark:text-violet-400">
                      {pu.full_name
                        ? pu.full_name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase()
                        : pu.email.slice(0, 2).toUpperCase()}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-[var(--ink)] truncate">
                      {pu.full_name || pu.email}
                    </p>
                    <p className="text-xs text-[var(--ink-muted)] truncate">
                      {pu.company || pu.email}
                    </p>
                  </div>
                  <div className="flex gap-3 text-xs text-[var(--ink-secondary)] flex-shrink-0">
                    <span title="Logins 14d">
                      <span className="font-medium text-violet-600">{pu.logins_14d}</span> logins
                    </span>
                    <span title="Pipeline items">
                      <span className="font-medium text-violet-600">{pu.pipeline_count}</span> pipeline
                    </span>
                    <span title="Alertas ativos">
                      <span className="font-medium text-violet-600">{pu.alert_count}</span> alertas
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
