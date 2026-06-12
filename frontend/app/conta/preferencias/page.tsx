"use client";

import { Shield } from "lucide-react";
import { useAuth } from "../../components/AuthProvider";
import { SectorAffinitySettings } from "../../components/SectorAffinitySettings";
import { NetworkAnalyticsToggle } from "../../configuracoes/components/NetworkAnalyticsToggle";

/**
 * FEEDBACK-005: Preferências page that hosts the SectorAffinitySettings component.
 * NETINT-006: Added NetworkAnalyticsToggle for privacy opt-in/opt-out.
 */
export default function PreferenciasPage() {
  const { session } = useAuth();

  if (!session?.access_token) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-sm text-[var(--ink-muted)]">Faça login para gerenciar suas preferências.</p>
      </div>
    );
  }

  return (
    <div className="space-y-10">
      {/* Privacy section — NETINT-006 */}
      <section aria-label="Privacidade">
        <div className="flex items-center gap-2 mb-1">
          <Shield
            className="w-5 h-5 text-[var(--ink-secondary)]"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <h2 className="text-xl font-bold text-[var(--ink)]">Privacidade</h2>
        </div>
        <p className="text-sm text-[var(--ink-secondary)] mb-2">
          Controle como seus dados de uso contribuem para melhorar os sinais de mercado para todos.
        </p>
        <div className="p-4 rounded-lg bg-[var(--surface-1)] border border-[var(--border-color)]">
          <NetworkAnalyticsToggle accessToken={session.access_token} />
        </div>
      </section>

      {/* Sector preferences — FEEDBACK-005 */}
      <SectorAffinitySettings accessToken={session.access_token} />
    </div>
  );
}
