"use client";

import { useAuth } from "../../components/AuthProvider";
import { SectorAffinitySettings } from "../../components/SectorAffinitySettings";

/** FEEDBACK-005: Preferências page that hosts the SectorAffinitySettings component. */
export default function PreferenciasPage() {
  const { session } = useAuth();

  if (!session?.access_token) {
    return (
      <div className="flex items-center justify-center py-16">
        <p className="text-sm text-[var(--ink-muted)]">Faça login para gerenciar suas preferências.</p>
      </div>
    );
  }

  return <SectorAffinitySettings accessToken={session.access_token} />;
}
