"use client";

import { useState } from "react";
import { useBackendStatusContext } from "./BackendStatusIndicator";

// ============================================================================
// DegradationBanner — Global banner for backend offline / recovering.
//
// Renders a sticky banner at the top of the viewport when the backend is
// detected as offline or recovering. Fully dismissible for the current
// session (re-appears on next navigation or page reload).
//
// Integrates with BackendStatusProvider's shared polling (CRIT-018 AC7).
// ============================================================================

const BANNER_DISMISS_KEY = "degradation-banner-dismissed";

interface DegradationBannerButtonProps {
  onClick: () => void;
  children: React.ReactNode;
}

function DegradationBannerButton({ onClick, children }: DegradationBannerButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="
        inline-flex items-center gap-1.5 shrink-0
        px-3 py-1.5 rounded-button text-sm font-medium
        border border-current/30
        hover:bg-white/20 dark:hover:bg-black/20
        transition-colors focus-visible:outline-none focus-visible:ring-2
        focus-visible:ring-offset-2 focus-visible:ring-white/50
      "
    >
      {children}
    </button>
  );
}

export function DegradationBanner() {
  const { status } = useBackendStatusContext();
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined") return false;
    try {
      return sessionStorage.getItem(BANNER_DISMISS_KEY) === "true";
    } catch {
      return false;
    }
  });

  // Only show when offline or recovering
  if (status === "online" || dismissed) return null;

  const isOffline = status === "offline";

  const handleDismiss = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem(BANNER_DISMISS_KEY, "true");
    } catch { /* noop */ }
  };

  return (
    <div
      role="alert"
      aria-live="polite"
      data-testid="degradation-banner"
      className={[
        "sticky top-0 z-50 w-full px-4 py-3 text-sm",
        "backdrop-blur-md shadow-md",
        "transition-all duration-300 animate-fade-in-down",
        isOffline
          ? "bg-red-600/90 text-white dark:bg-red-800/90"
          : "bg-amber-500/90 text-white dark:bg-amber-700/90",
      ].join(" ")}
    >
      <div className="max-w-7xl mx-auto flex items-start sm:items-center gap-3">
        {/* Icon */}
        <svg
          className="w-5 h-5 shrink-0 mt-0.5 sm:mt-0"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          aria-hidden="true"
        >
          {isOffline ? (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          ) : (
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          )}
        </svg>

        {/* Message */}
        <div className="flex-1 min-w-0">
          <p className="font-semibold">
            {isOffline
              ? "Backend temporariamente indisponivel"
              : "Backend recuperado — normalizando"}
          </p>
          <p className="text-xs opacity-90 mt-0.5">
            {isOffline
              ? "Algumas funcionalidades podem estar limitadas. Dados em cache ainda estao disponiveis. Reconexao automatica em andamento."
              : "Servico restabelecido. Funcionalidades voltando ao normal."}
          </p>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 shrink-0">
          {isOffline && (
            <DegradationBannerButton onClick={() => window.location.reload()}>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Recarregar
            </DegradationBannerButton>
          )}
          <DegradationBannerButton onClick={handleDismiss}>
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Dispensar
          </DegradationBannerButton>
        </div>
      </div>
    </div>
  );
}

export default DegradationBanner;
