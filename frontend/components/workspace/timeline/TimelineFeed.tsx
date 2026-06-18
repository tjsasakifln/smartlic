"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { TimelineEvento, TimelineEventoCard } from "./TimelineEventoCard";
import { TimelineFiltros } from "./TimelineFiltros";
import { EventoManualForm } from "./EventoManualForm";

interface TimelineFeedProps {
  editalId: string;
}

const LIMIT = 50;

export function TimelineFeed({ editalId }: TimelineFeedProps) {
  const [eventos, setEventos] = useState<TimelineEvento[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);

  // Filters
  const [selectedTipos, setSelectedTipos] = useState<string[]>([]);
  const [apenasCriticos, setApenasCriticos] = useState(false);
  const [dataInicio, setDataInicio] = useState("");
  const [dataFim, setDataFim] = useState("");

  const sentinelRef = useRef<HTMLDivElement>(null);
  const fetchedRef = useRef(false);

  const buildUrl = useCallback(
    (offsetVal: number) => {
      const params = new URLSearchParams();
      params.set("limit", String(LIMIT));
      params.set("offset", String(offsetVal));

      if (selectedTipos.length === 1) {
        params.set("tipo_evento", selectedTipos[0]);
      }
      if (apenasCriticos) {
        params.set("critico", "true");
      }
      if (dataInicio) params.set("data_inicio", dataInicio);
      if (dataFim) params.set("data_fim", dataFim);

      return `/api/workspace/timeline/${editalId}?${params.toString()}`;
    },
    [editalId, selectedTipos, apenasCriticos, dataInicio, dataFim],
  );

  const fetchEventos = useCallback(
    async (offsetVal: number, append: boolean) => {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }
      setError(null);

      try {
        const res = await fetch(buildUrl(offsetVal));
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.message || "Erro ao carregar eventos.");
        }

        const data = await res.json();
        const novos = data.eventos ?? [];

        if (append) {
          setEventos((prev) => [...prev, ...novos]);
        } else {
          setEventos(novos);
        }

        setTotal(data.total ?? 0);
        setOffset(offsetVal + novos.length);
        setHasMore(novos.length === LIMIT);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Erro ao carregar eventos.");
      } finally {
        setLoading(false);
        setLoadingMore(false);
        fetchedRef.current = true;
      }
    },
    [buildUrl],
  );

  // Load on mount and when filters change
  useEffect(() => {
    setOffset(0);
    setHasMore(true);
    fetchedRef.current = false;
    fetchEventos(0, false);
  }, [fetchEventos]);

  // Infinite scroll via IntersectionObserver
  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || loading || loadingMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting && hasMore && !loadingMore && !loading) {
          fetchEventos(offset, true);
        }
      },
      { threshold: 0.1 },
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loading, loadingMore, offset, fetchEventos]);

  // Refresh handler for EventoManualForm
  const handleEventoCreated = useCallback(() => {
    setOffset(0);
    setHasMore(true);
    fetchedRef.current = false;
    fetchEventos(0, false);
  }, [fetchEventos]);

  return (
    <div className="space-y-6">
      {/* Filtros */}
      <TimelineFiltros
        selectedTipos={selectedTipos}
        onToggleTipo={(tipo) =>
          setSelectedTipos((prev) =>
            prev.includes(tipo)
              ? prev.filter((t) => t !== tipo)
              : [...prev, tipo],
          )
        }
        apenasCriticos={apenasCriticos}
        onToggleCriticos={() => setApenasCriticos((p) => !p)}
        dataInicio={dataInicio}
        onDataInicioChange={setDataInicio}
        dataFim={dataFim}
        onDataFimChange={setDataFim}
      />

      {/* Form de criacao */}
      <EventoManualForm editalId={editalId} onCreated={handleEventoCreated} />

      {/* Loading state */}
      {loading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-24 rounded-xl bg-[var(--surface-2)] animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div className="p-6 text-center rounded-xl border border-red-200 bg-red-50">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={() => fetchEventos(0, false)}
            className="mt-3 text-sm text-[var(--brand-blue)] hover:underline"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && eventos.length === 0 && (
        <div className="p-12 text-center rounded-xl border border-dashed border-[var(--border)]">
          <p className="text-sm text-[var(--ink-secondary)]">
            Nenhum evento na timeline ainda.
          </p>
          <p className="text-xs text-[var(--ink-tertiary)] mt-1">
            Adicione notas e lembretes para acompanhar o edital.
          </p>
        </div>
      )}

      {/* Timeline feed */}
      {eventos.length > 0 && (
        <div className="space-y-3">
          {eventos.map((evento) => (
            <TimelineEventoCard key={evento.id} evento={evento} />
          ))}

          {/* Infinite scroll sentinel */}
          <div ref={sentinelRef} className="h-4" />

          {loadingMore && (
            <div className="flex justify-center py-4">
              <div className="w-6 h-6 border-2 border-[var(--brand-blue)] border-t-transparent rounded-full animate-spin" />
            </div>
          )}

          {!hasMore && eventos.length > 0 && (
            <p className="text-center text-xs text-[var(--ink-tertiary)] py-4">
              Todos os {total} eventos carregados.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
