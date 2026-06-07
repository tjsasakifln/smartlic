"use client";

import { useState, useEffect, useCallback } from "react";
import { SlidersHorizontal, Loader2 } from "lucide-react";
import { useAuth } from "../../components/AuthProvider";

/** FEEDBACK-005: Sector affinity data from GET /v1/profile/sector-affinity. */
interface SectorAffinity {
  sector_id: string;
  sector_name: string;
  affinity_score: number;
  muted: boolean;
}

/** FEEDBACK-005: "Setores que não me interessam" — mute/unmute sector preferences. */
export default function PreferenciasPage() {
  const { session } = useAuth();
  const [sectors, setSectors] = useState<SectorAffinity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);

  const fetchAffinities = useCallback(async () => {
    if (!session?.access_token) return;
    try {
      setError(null);
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/v1/profile/sector-affinity`,
        { headers: { Authorization: `Bearer ${session.access_token}` } },
      );
      if (!res.ok) throw new Error("Falha ao carregar preferências");
      const data: SectorAffinity[] = await res.json();
      setSectors(data);
    } catch (err) {
      setError("Não foi possível carregar suas preferências. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }, [session?.access_token]);

  useEffect(() => {
    fetchAffinities();
  }, [fetchAffinities]);

  const handleToggle = async (sectorId: string, currentMuted: boolean) => {
    if (!session?.access_token) return;
    setToggling(sectorId);
    const newMuted = !currentMuted;

    // Optimistic update
    setSectors((prev) =>
      prev.map((s) =>
        s.sector_id === sectorId ? { ...s, muted: newMuted } : s,
      ),
    );

    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/v1/profile/sector-affinity/${sectorId}`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${session.access_token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ muted: newMuted }),
        },
      );
      if (!res.ok) throw new Error("Falha ao atualizar preferência");

      // Refresh to get server-side affinity_score
      const updated: SectorAffinity = await res.json();
      setSectors((prev) =>
        prev.map((s) =>
          s.sector_id === sectorId
            ? { ...s, affinity_score: updated.affinity_score, muted: updated.muted }
            : s,
        ),
      );
    } catch {
      // Revert on failure
      setSectors((prev) =>
        prev.map((s) =>
          s.sector_id === sectorId ? { ...s, muted: currentMuted } : s,
        ),
      );
    } finally {
      setToggling(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="w-6 h-6 animate-spin text-[var(--ink-muted)]" />
        <span className="ml-2 text-[var(--ink-muted)]">Carregando preferências...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16">
        <p className="text-red-600 dark:text-red-400 mb-4">{error}</p>
        <button
          onClick={fetchAffinities}
          className="text-sm font-medium text-[var(--brand-navy)] hover:underline"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  const mutedSectors = sectors.filter((s) => s.muted);
  const activeSectors = sectors.filter((s) => !s.muted);

  return (
    <div className="space-y-8" data-testid="preferencias-page">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <SlidersHorizontal
            className="w-5 h-5 text-[var(--ink-secondary)]"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <h1 className="text-xl font-bold text-[var(--ink)]">Preferências</h1>
        </div>
        <p className="text-sm text-[var(--ink-secondary)]">
          Personalize os setores que mais interessam. Setores silenciados têm peso reduzido nos resultados.
        </p>
      </div>

      {/* Muted sectors section */}
      {mutedSectors.length > 0 && (
        <section aria-label="Setores silenciados">
          <h2 className="text-sm font-semibold text-[var(--ink-muted)] uppercase tracking-wide mb-3">
            Setores que não me interessam
          </h2>
          <ul className="space-y-2">
            {mutedSectors.map((sector) => (
              <li
                key={sector.sector_id}
                className="flex items-center justify-between p-3 rounded-lg bg-[var(--surface-1)] border border-[var(--border-color)]"
                data-testid={`sector-row-${sector.sector_id}`}
              >
                <span className="text-sm font-medium text-[var(--ink-muted)] line-through">
                  {sector.sector_name}
                </span>
                <button
                  onClick={() => handleToggle(sector.sector_id, true)}
                  disabled={toggling === sector.sector_id}
                  className="text-xs font-medium text-[var(--brand-navy)] hover:underline disabled:opacity-50"
                  data-testid={`unmute-${sector.sector_id}`}
                >
                  {toggling === sector.sector_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    "Reativar"
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Active sectors */}
      <section aria-label="Setores ativos">
        <h2 className="text-sm font-semibold text-[var(--ink-muted)] uppercase tracking-wide mb-3">
          Setores ativos
        </h2>
        {sectors.length === 0 ? (
          <p className="text-sm text-[var(--ink-secondary)] py-6 text-center">
            Nenhuma preferência de setor encontrada. Comece a buscar para que suas preferências sejam detectadas automaticamente.
          </p>
        ) : (
          <ul className="space-y-2">
            {activeSectors.map((sector) => (
              <li
                key={sector.sector_id}
                className="flex items-center justify-between p-3 rounded-lg bg-[var(--surface-1)] border border-[var(--border-color)]"
                data-testid={`sector-row-${sector.sector_id}`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-sm font-medium text-[var(--ink)] truncate">
                    {sector.sector_name}
                  </span>
                  <span className="text-xs text-[var(--ink-muted)]">
                    Afinidade: {Math.round(sector.affinity_score * 100)}%
                  </span>
                </div>
                <button
                  onClick={() => handleToggle(sector.sector_id, false)}
                  disabled={toggling === sector.sector_id}
                  className="text-xs font-medium text-[var(--ink-muted)] hover:text-red-600 hover:underline disabled:opacity-50 flex-shrink-0 ml-3"
                  data-testid={`mute-${sector.sector_id}`}
                >
                  {toggling === sector.sector_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    "Silenciar"
                  )}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Footer note */}
      <p className="text-xs text-[var(--ink-muted)] pt-4 border-t border-[var(--border-color)]">
        Setores silenciados nunca são removidos — apenas têm influência reduzida nos resultados. Você pode reativá-los a qualquer momento.
      </p>
    </div>
  );
}
