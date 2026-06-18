"use client";

import { useState, useEffect, useCallback } from "react";
import { Bell } from "lucide-react";

interface AlertaBadgeProps {
  /** Additional CSS classes for the icon. */
  className?: string;
  /** Called when badge is clicked. */
  onClick?: () => void;
}

/**
 * AlertaBadge — Displays unread alert count as a bell icon with badge.
 *
 * Fetches /api/workspace/alertas/unread-count on mount and every 60s.
 * Can be embedded in NavigationShell, Sidebar, or BottomNav.
 */
export function AlertaBadge({ className = "", onClick }: AlertaBadgeProps) {
  const [count, setCount] = useState(0);
  const [loading, setLoading] = useState(true);

  const fetchCount = useCallback(async () => {
    try {
      const res = await fetch("/api/workspace/alertas/unread-count");
      if (res.ok) {
        const data = await res.json();
        setCount(data.unread_count ?? 0);
      }
    } catch {
      // Silently fail — badge shows 0
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCount();

    // Poll every 60 seconds
    const interval = setInterval(fetchCount, 60_000);
    return () => clearInterval(interval);
  }, [fetchCount]);

  // Expose a manual refresh method via custom event
  useEffect(() => {
    const handler = () => fetchCount();
    window.addEventListener("alertas-refresh", handler);
    return () => window.removeEventListener("alertas-refresh", handler);
  }, [fetchCount]);

  return (
    <button
      onClick={onClick}
      className={`relative inline-flex items-center justify-center ${className}`}
      aria-label={`Alertas${count > 0 ? `: ${count} não lidos` : ""}`}
    >
      <Bell className="w-5 h-5" aria-hidden="true" />

      {!loading && count > 0 && (
        <span
          className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold leading-none shadow-sm"
          data-testid="alerta-badge-count"
        >
          {count > 99 ? "99+" : count}
        </span>
      )}
    </button>
  );
}
