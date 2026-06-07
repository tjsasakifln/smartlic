"use client";

import { useState, useEffect, useCallback } from "react";
import { SlidersHorizontal, Loader2, VolumeX, Volume2 } from "lucide-react";

/**
 * FEEDBACK-005: Single sector affinity item from the backend.
 */
interface SectorAffinity {
  sector_id: string;
  sector_name: string;
  affinity_score: number;
  muted: boolean;
}

/**
 * FEEDBACK-005: "Setores que não me interessam" — mute/unmute sector preferences.
 *
 * Fetches from GET /v1/profile/sector-affinity and allows toggling via PATCH.
 * Fires Mixpanel events `sector_muted` and `sector_unmuted` on toggle.
 */
export function SectorAffinitySettings({ accessToken }: { accessToken: string }) {
  const [sectors, setSectors] = useState<SectorAffinity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [toggling, setToggling] = useState<string | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const fireMixpanel = useCallback((event: string, props: Record<string, unknown>) => {
    if (typeof window !== "undefined" && window.mixpanel) {
      try {
        window.mixpanel.track(event, props);
      } catch {
        // Best-effort analytics
      }
    }
  }, []);

  const fetchAffinities = useCallback(async () => {
    if (!accessToken) return;
    try {
      setError(null);
      setLoading(true);
      const res = await fetch(
        `${apiUrl}/v1/profile/sector-affinity`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!res.ok) throw new Error("Falha ao carregar preferências");
      const data: SectorAffinity[] = await res.json();
      setSectors(data);
    } catch {
      setError("Não foi possível carregar suas preferências. Tente novamente.");
    } finally {
      setLoading(false);
    }
  }, [accessToken, apiUrl]);

  useEffect(() => {
    fetchAffinities();
  }, [fetchAffinities]);

  const handleToggle = async (sectorId: string, sectorName: string, currentMuted: boolean) => {
    if (!accessToken) return;
    setToggling(sectorId);
    const newMuted = !currentMuted;

    // Optimistic update
    setSectors((prev) =>
      prev.map((s) =>
        s.sector_id === sectorId ? { ...s, muted: newMuted } : s,
      ),
    );

    // Fire Mixpanel event immediately for responsiveness
    fireMixpanel(newMuted ? "sector_muted" : "sector_unmuted", { sector_id: sectorId, sector_name: sectorName });

    try {
      const res = await fetch(
        `${apiUrl}/v1/profile/sector-affinity/${sectorId}`,
        {
          method: "PATCH",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ muted: newMuted }),
        },
      );
      if (!res.ok) throw new Error("Falha ao atualizar preferência");

      // Refresh from server to get the new affinity_score
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
        <span className="ml-2 text-sm text-[var(--ink-muted)]">Carregando preferências...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16" data-testid="sector-affinity-error">
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
    <div className="space-y-8" data-testid="sector-affinity-settings">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <SlidersHorizontal
            className="w-5 h-5 text-[var(--ink-secondary)]"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <h2 className="text-xl font-bold text-[var(--ink)]">Preferências de Setores</h2>
        </div>
        <p className="text-sm text-[var(--ink-secondary)]">
          Personalize os setores que mais interessam. Setores silenciados têm peso reduzido nos resultados.
        </p>
      </div>

      {/* Muted sectors section */}
      {mutedSectors.length > 0 && (
        <section aria-label="Setores silenciados">
          <h3 className="text-sm font-semibold text-[var(--ink-muted)] uppercase tracking-wide mb-3">
            Setores que não me interessam
          </h3>
          <ul className="space-y-2">
            {mutedSectors.map((sector) => (
              <li
                key={sector.sector_id}
                className="flex items-center justify-between p-3 rounded-lg bg-[var(--surface-1)] border border-[var(--border-color)]"
                data-testid={`sector-row-${sector.sector_id}`}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <VolumeX className="w-4 h-4 text-[var(--ink-muted)] flex-shrink-0" aria-hidden="true" />
                  <span className="text-sm font-medium text-[var(--ink-muted)] line-through truncate">
                    {sector.sector_name}
                  </span>
                </div>
                <button
                  onClick={() => handleToggle(sector.sector_id, sector.sector_name, true)}
                  disabled={toggling === sector.sector_id}
                  className="flex items-center gap-1 text-xs font-medium text-[var(--brand-navy)] hover:underline disabled:opacity-50 flex-shrink-0 ml-3"
                  data-testid={`unmute-${sector.sector_id}`}
                >
                  {toggling === sector.sector_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <Volume2 className="w-3.5 h-3.5" />
                      Reativar
                    </>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Active sectors */}
      {activeSectors.length > 0 && (
        <section aria-label="Setores ativos">
          <h3 className="text-sm font-semibold text-[var(--ink-muted)] uppercase tracking-wide mb-3">
            Setores ativos
          </h3>
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
                  <span className="text-xs text-[var(--ink-muted)] whitespace-nowrap">
                    Afinidade: {Math.round(sector.affinity_score * 100)}%
                  </span>
                </div>
                <button
                  onClick={() => handleToggle(sector.sector_id, sector.sector_name, false)}
                  disabled={toggling === sector.sector_id}
                  className="flex items-center gap-1 text-xs font-medium text-[var(--ink-muted)] hover:text-red-600 hover:underline disabled:opacity-50 flex-shrink-0 ml-3"
                  data-testid={`mute-${sector.sector_id}`}
                >
                  {toggling === sector.sector_id ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <>
                      <VolumeX className="w-3.5 h-3.5" />
                      Silenciar
                    </>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Empty state */}
      {sectors.length === 0 && (
        <section aria-label="Nenhuma preferência">
          <p className="text-sm text-[var(--ink-secondary)] py-6 text-center">
            Nenhuma preferência de setor encontrada. Comece a buscar para que suas preferências sejam detectadas automaticamente.
          </p>
        </section>
      )}

      {/* Footer note */}
      <p className="text-xs text-[var(--ink-muted)] pt-4 border-t border-[var(--border-color)]">
        Setores silenciados nunca são removidos — apenas têm influência reduzida nos resultados. Você pode reativá-los a qualquer momento.
      </p>
    </div>
  );
}
