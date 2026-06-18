"use client";

import { useState, useEffect, useCallback } from "react";
import { Bell, Filter, ChevronLeft, ChevronRight, AlertTriangle } from "lucide-react";
import { AlertaCard } from "../../../components/workspace/AlertaCard";
import { EmptyState } from "../../../components/EmptyState";

interface AlertaItem {
  id: string;
  tipo: string;
  titulo: string;
  descricao?: string;
  lido: boolean;
  created_at: string;
  metadata?: Record<string, unknown>;
}

interface AlertasResponse {
  alertas: AlertaItem[];
  total: number;
  limit: number;
  offset: number;
}

const PAGE_SIZE = 20;

const TIPO_FILTERS = [
  { value: "", label: "Todos" },
  { value: "new_matching_edital", label: "Novos Editais" },
  { value: "deadline_approaching", label: "Prazos" },
  { value: "pregao_starting", label: "Pregões" },
  { value: "result_published", label: "Resultados" },
  { value: "contrato_firmado", label: "Contratos" },
];

const STATUS_FILTERS = [
  { value: "", label: "Todos" },
  { value: "false", label: "Não lidos" },
  { value: "true", label: "Lidos" },
];

/**
 * Workspace Alertas page — full-page list of user alerts.
 */
export default function WorkspaceAlertasPage() {
  const [alertas, setAlertas] = useState<AlertaItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [tipoFilter, setTipoFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const fetchAlertas = useCallback(async () => {
    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String(page * PAGE_SIZE));
    if (tipoFilter) params.set("type", tipoFilter);
    if (statusFilter) params.set("status", statusFilter);

    try {
      const res = await fetch(`/api/workspace/alertas?${params}`);
      if (!res.ok) throw new Error("Erro ao carregar alertas");

      const data: AlertasResponse = await res.json();
      setAlertas(data.alertas || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  }, [page, tipoFilter, statusFilter]);

  useEffect(() => {
    fetchAlertas();
  }, [fetchAlertas]);

  const handleMarkRead = (id: string) => {
    setAlertas((prev: AlertaItem[]) =>
      prev.map((a: AlertaItem) => (a.id === id ? { ...a, lido: true } : a))
    );
    // Dispatch refresh event for badge
    window.dispatchEvent(new Event("alertas-refresh"));
  };

  const totalPages = Math.ceil(total / PAGE_SIZE);

  return (
    <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Bell className="w-6 h-6 text-[var(--brand-blue)]" />
        <div>
          <h1 className="text-xl font-bold text-[var(--ink)]">Alertas</h1>
          <p className="text-sm text-[var(--ink-muted)]">
            {total} alerta{total !== 1 ? "s" : ""} no total
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <Filter className="w-4 h-4 text-[var(--ink-muted)]" />
        <select
          value={tipoFilter}
          onChange={(e) => {
            setTipoFilter(e.target.value);
            setPage(0);
          }}
          className="px-3 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--surface-0)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]"
          aria-label="Filtrar por tipo"
        >
          {TIPO_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>

        <select
          value={statusFilter}
          onChange={(e) => {
            setStatusFilter(e.target.value);
            setPage(0);
          }}
          className="px-3 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--surface-0)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]"
          aria-label="Filtrar por status"
        >
          {STATUS_FILTERS.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
      </div>

      {/* Error state */}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-sm">
          <AlertTriangle className="w-5 h-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div
              key={i}
              className="h-24 rounded-lg bg-gray-100 dark:bg-gray-800 animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Alert list */}
      {!loading && !error && alertas.length === 0 && (
        <EmptyState
          icon={<Bell className="w-12 h-12 text-[var(--ink-faint)]" />}
          title="Nenhum alerta encontrado"
          description={
            tipoFilter || statusFilter
              ? "Tente alterar os filtros para ver mais resultados."
              : "Você ainda não tem alertas. Adicione editais à sua watchlist para começar a receber notificações."
          }
        />
      )}

      {!loading && alertas.length > 0 && (
        <div className="space-y-2">
          {alertas.map((alerta) => (
            <AlertaCard
              key={alerta.id}
              alerta={alerta}
              onMarkRead={handleMarkRead}
            />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-4 pt-2">
          <button
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={page === 0}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md border border-[var(--border)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--surface-1)] transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            <span>Anterior</span>
          </button>

          <span className="text-sm text-[var(--ink-muted)]">
            Página {page + 1} de {totalPages}
          </span>

          <button
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={page >= totalPages - 1}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-md border border-[var(--border)] disabled:opacity-40 disabled:cursor-not-allowed hover:bg-[var(--surface-1)] transition-colors"
          >
            <span>Próxima</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
}
