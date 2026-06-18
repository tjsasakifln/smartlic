"use client";

import { useState, useEffect, useCallback } from "react";
import { Plus, Trash2, Search, AlertTriangle } from "lucide-react";

interface WatchlistItem {
  id: string;
  edital_id: string;
  uf: string;
  setor: string;
  keywords: string[];
  created_at: string;
}

interface WatchlistPanelProps {
  /** Called when watchlist changes (e.g. to refresh badge count). */
  onChange?: () => void;
}

/**
 * WatchlistPanel — manage watched editais for alert monitoring.
 *
 * Desktop sidebar panel that displays the user's watchlist
 * and allows adding/removing watched editais.
 */
export function WatchlistPanel({ onChange }: WatchlistPanelProps) {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New item form
  const [editalId, setEditalId] = useState("");
  const [uf, setUf] = useState("");
  const [setor, setSetor] = useState("");
  const [keywords, setKeywords] = useState("");
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const fetchWatchlist = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/workspace/watchlist");
      if (!res.ok) {
        throw new Error("Erro ao carregar watchlist");
      }
      const data = await res.json();
      setItems(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWatchlist();
  }, [fetchWatchlist]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editalId.trim()) return;

    setAdding(true);
    try {
      const res = await fetch("/api/workspace/watchlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          edital_id: editalId.trim(),
          uf: uf.trim().toUpperCase(),
          setor: setor.trim(),
          keywords: keywords
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean),
        }),
      });

      if (!res.ok) throw new Error("Erro ao adicionar");

      // Reset form
      setEditalId("");
      setUf("");
      setSetor("");
      setKeywords("");
      setShowForm(false);

      // Refresh list
      await fetchWatchlist();
      onChange?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao adicionar");
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (id: string) => {
    try {
      const res = await fetch(`/api/workspace/watchlist/${id}`, {
        method: "DELETE",
      });

      if (!res.ok) throw new Error("Erro ao remover");

      setItems((prev) => prev.filter((item) => item.id !== id));
      onChange?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao remover");
    }
  };

  if (loading) {
    return (
      <div className="p-4 space-y-3">
        <div className="h-5 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        <div className="h-16 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
        <div className="h-16 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-[var(--ink)]">
          Editais Monitorados
        </h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-1 text-xs font-medium text-[var(--brand-blue)] hover:text-[var(--brand-blue-dark)] transition-colors"
          aria-label="Adicionar edital à watchlist"
        >
          <Plus className="w-4 h-4" />
          <span>Adicionar</span>
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-2 rounded-lg bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Add form */}
      {showForm && (
        <form onSubmit={handleAdd} className="space-y-2 p-3 rounded-lg bg-[var(--surface-1)] border border-[var(--border)]">
          <div>
            <label htmlFor="wl-edital-id" className="block text-xs font-medium text-[var(--ink-secondary)] mb-1">
              ID do Edital *
            </label>
            <input
              id="wl-edital-id"
              type="text"
              value={editalId}
              onChange={(e) => setEditalId(e.target.value)}
              placeholder="PNCP ID ou identificador"
              required
              className="w-full px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--surface-0)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label htmlFor="wl-uf" className="block text-xs font-medium text-[var(--ink-secondary)] mb-1">
                UF
              </label>
              <input
                id="wl-uf"
                type="text"
                value={uf}
                onChange={(e) => setUf(e.target.value)}
                placeholder="SP, RJ, MG..."
                maxLength={2}
                className="w-full px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--surface-0)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]"
              />
            </div>
            <div>
              <label htmlFor="wl-setor" className="block text-xs font-medium text-[var(--ink-secondary)] mb-1">
                Setor
              </label>
              <input
                id="wl-setor"
                type="text"
                value={setor}
                onChange={(e) => setSetor(e.target.value)}
                placeholder="Ex: informatica"
                className="w-full px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--surface-0)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]"
              />
            </div>
          </div>
          <div>
            <label htmlFor="wl-keywords" className="block text-xs font-medium text-[var(--ink-secondary)] mb-1">
              Palavras-chave (separadas por v&iacute;rgula)
            </label>
            <input
              id="wl-keywords"
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="rede, cabeamento, switch"
              className="w-full px-2 py-1.5 text-sm rounded-md border border-[var(--border)] bg-[var(--surface-0)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]"
            />
          </div>
          <div className="flex gap-2 pt-1">
            <button
              type="submit"
              disabled={adding || !editalId.trim()}
              className="flex-1 px-3 py-1.5 text-xs font-medium text-white bg-[var(--brand-blue)] rounded-md hover:opacity-90 disabled:opacity-50 transition-opacity"
            >
              {adding ? "Adicionando..." : "Adicionar"}
            </button>
            <button
              type="button"
              onClick={() => setShowForm(false)}
              className="px-3 py-1.5 text-xs font-medium text-[var(--ink-secondary)] hover:text-[var(--ink)] transition-colors"
            >
              Cancelar
            </button>
          </div>
        </form>
      )}

      {/* Watchlist items */}
      {items.length === 0 && !loading ? (
        <div className="flex flex-col items-center gap-2 py-6 text-center">
          <Search className="w-8 h-8 text-[var(--ink-faint)]" />
          <p className="text-sm text-[var(--ink-muted)]">
            Nenhum edital monitorado ainda.
          </p>
          <p className="text-xs text-[var(--ink-faint)]">
            Adicione editais para receber alertas de novos matches.
          </p>
        </div>
      ) : (
        <div className="space-y-2 max-h-[400px] overflow-y-auto">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-start gap-2 p-2.5 rounded-lg border border-[var(--border)] bg-[var(--surface-0)] hover:bg-[var(--surface-1)] transition-colors group"
            >
              <div className="flex-1 min-w-0">
                <p className="text-xs font-medium text-[var(--ink)] truncate">
                  {item.edital_id}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  {item.uf && (
                    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-[var(--brand-blue-subtle)] text-[var(--brand-blue)]">
                      {item.uf}
                    </span>
                  )}
                  {item.setor && (
                    <span className="text-[10px] text-[var(--ink-muted)]">
                      {item.setor}
                    </span>
                  )}
                </div>
                {item.keywords && item.keywords.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1">
                    {item.keywords.slice(0, 3).map((kw, i) => (
                      <span
                        key={i}
                        className="text-[10px] px-1 py-0.5 rounded bg-gray-100 dark:bg-gray-800 text-[var(--ink-muted)]"
                      >
                        {kw}
                      </span>
                    ))}
                    {item.keywords.length > 3 && (
                      <span className="text-[10px] text-[var(--ink-faint)]">
                        +{item.keywords.length - 3}
                      </span>
                    )}
                  </div>
                )}
              </div>
              <button
                onClick={() => handleRemove(item.id)}
                className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-50 dark:hover:bg-red-900/20 text-[var(--ink-faint)] hover:text-red-500 transition-all"
                aria-label={`Remover ${item.edital_id} da watchlist`}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
