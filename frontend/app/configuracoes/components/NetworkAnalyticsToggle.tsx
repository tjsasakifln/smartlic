"use client";

import { useState, useEffect, useCallback } from "react";
import { Info, Loader2 } from "lucide-react";

/**
 * NETINT-006: Network analytics opt-in/opt-out toggle.
 *
 * Allows users to control whether anonymized usage data is collected
 * for network intelligence features. LGPD-compliant opt-in (Art. 9).
 *
 * States:
 *   Loading  — Skeleton while fetching current preference
 *   null     — Undecided (neutral toggle, tooltip "Voce ainda nao optou")
 *   true     — Opted in (green, tooltip "Contribuindo com dados anonimos")
 *   false    — Opted out (inactive, tooltip "Contribuicao desativada")
 *   Error    — Silent fallback (toggle keeps last known state)
 *
 * Optimistic: toggle responds immediately, PATCH is async.
 * Rollback: if PATCH fails, visual state reverts.
 */

interface NetworkAnalyticsToggleProps {
  accessToken: string;
}

export function NetworkAnalyticsToggle({ accessToken }: NetworkAnalyticsToggleProps) {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [tooltipText, setTooltipText] = useState("");

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const getTooltip = (val: boolean | null): string => {
    if (val === null) return "Voce ainda nao optou por contribuir com dados anonimos.";
    if (val === true) return "Contribuindo com dados anonimos de uso para melhorar os sinais de mercado.";
    return "Contribuicao desativada. Nenhum dado de uso e coletado.";
  };

  const fetchPreference = useCallback(async () => {
    if (!accessToken) return;
    try {
      setLoading(true);
      const res = await fetch(
        `${apiUrl}/v1/me`,
        { headers: { Authorization: `Bearer ${accessToken}` } },
      );
      if (!res.ok) throw new Error("Falha ao carregar preferencia");
      const data = await res.json();
      // allow_network_analytics is on the full profile object
      const value = data.allow_network_analytics ?? null;
      setEnabled(value);
      setTooltipText(getTooltip(value));
    } catch {
      // Silent fallback
      setEnabled(null);
      setTooltipText(getTooltip(null));
    } finally {
      setLoading(false);
    }
  }, [accessToken, apiUrl]);

  useEffect(() => {
    fetchPreference();
  }, [fetchPreference]);

  const handleToggle = async () => {
    if (!accessToken || saving) return;
    const newValue = !enabled;
    const previousValue = enabled;

    // Optimistic update
    setEnabled(newValue);
    setTooltipText(getTooltip(newValue));
    setSaving(true);

    try {
      const res = await fetch(
        `${apiUrl}/v1/profile/network-analytics`,
        {
          method: "PUT",
          headers: {
            Authorization: `Bearer ${accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({ allow_network_analytics: newValue }),
        },
      );
      if (!res.ok) throw new Error("Falha ao salvar preferencia");

      const result = await res.json();
      setEnabled(result.allow_network_analytics);
      setTooltipText(getTooltip(result.allow_network_analytics));
    } catch {
      // Rollback on error
      setEnabled(previousValue);
      setTooltipText(getTooltip(previousValue));
    } finally {
      setSaving(false);
    }
  };

  // ── Loading state ──────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-between py-3" data-testid="network-analytics-toggle">
        <div className="space-y-1">
          <div className="h-4 w-48 bg-[var(--surface-1)] rounded animate-pulse" />
          <div className="h-3 w-64 bg-[var(--surface-1)] rounded animate-pulse" />
        </div>
        <div className="h-6 w-11 bg-[var(--surface-1)] rounded-full animate-pulse" />
      </div>
    );
  }

  return (
    <div
      className="flex items-center justify-between py-3"
      data-testid="network-analytics-toggle"
    >
      {/* Label and tooltip */}
      <div className="flex flex-col gap-0.5 min-w-0 pr-4">
        <div className="flex items-center gap-1.5">
          <span className="text-sm font-medium text-[var(--ink)]">
            Contribuir com dados anonimos de uso
          </span>
          <span
            className="relative group cursor-help"
            aria-label={tooltipText}
            data-testid="toggle-tooltip"
          >
            <Info
              className="w-4 h-4 text-[var(--ink-muted)]"
              strokeWidth={1.5}
              aria-hidden="true"
            />
            <span
              className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-1.5
                         text-xs text-white bg-gray-800 rounded-md shadow-lg
                         opacity-0 group-hover:opacity-100 transition-opacity
                         whitespace-nowrap z-10 pointer-events-none"
              role="tooltip"
            >
              {tooltipText}
            </span>
          </span>
        </div>
        <p className="text-xs text-[var(--ink-muted)]">
          Apenas contagens anonimas de setores/UF — nunca dados pessoais ou CNPJ
        </p>
      </div>

      {/* Toggle switch */}
      <button
        type="button"
        role="switch"
        aria-checked={enabled === true}
        aria-label="Contribuir com dados anonimos de uso"
        disabled={saving}
        onClick={handleToggle}
        className={`
          relative inline-flex h-6 w-11 items-center rounded-full
          transition-colors duration-200 ease-in-out focus:outline-none
          focus:ring-2 focus:ring-[var(--brand-navy)] focus:ring-offset-2
          disabled:opacity-60 disabled:cursor-not-allowed flex-shrink-0
          ${enabled === true
            ? "bg-[var(--brand-navy)]"
            : "bg-[var(--surface-2)]"
          }
        `}
        data-testid="toggle-switch"
      >
        {saving ? (
          <span className="inline-flex items-center justify-center w-full">
            <Loader2 className="w-4 h-4 text-white animate-spin" />
          </span>
        ) : (
          <span
            className={`
              inline-block h-5 w-5 transform rounded-full bg-white shadow-sm
              ring-0 transition-transform duration-200 ease-in-out
              ${enabled === true ? "translate-x-[22px]" : "translate-x-[2px]"}
            `}
          />
        )}
      </button>
    </div>
  );
}
