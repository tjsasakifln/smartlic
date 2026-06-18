"use client";

import { Bell } from "lucide-react";

interface AlertasWidgetProps {
  unreadCount: number;
  loading: boolean;
}

/**
 * AlertasWidget — placeholder for B2GOPS-011.
 *
 * B2GOPS-010 (#2020): Shows unread alert count or empty state.
 * Full alert system will be implemented in B2GOPS-011.
 */
export function AlertasWidget({ unreadCount, loading }: AlertasWidgetProps) {
  return (
    <div className="bg-[var(--surface-0)] rounded-xl border border-[var(--border)] shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <Bell className="w-5 h-5 text-[var(--brand-blue)]" aria-hidden="true" />
          <h2 className="text-base font-semibold text-[var(--ink)]">Alertas</h2>
          {!loading && unreadCount > 0 && (
            <span className="inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-red-500 text-white text-xs font-bold">
              {unreadCount}
            </span>
          )}
        </div>
      </div>

      <div className="p-5">
        {loading ? (
          <div className="space-y-2">
            <div className="h-12 bg-[var(--surface-1)] animate-pulse rounded-lg" />
            <div className="h-12 bg-[var(--surface-1)] animate-pulse rounded-lg" />
          </div>
        ) : (
          <p className="text-sm text-[var(--ink-muted)] text-center py-4">
            {unreadCount > 0
              ? `Voce tem ${unreadCount} alerta(s) nao lido(s).`
              : "Nenhum alerta no momento. Configure seus alertas nas preferencias."}
          </p>
        )}
      </div>
    </div>
  );
}
