"use client";

import { useBackendStatusContext } from "../components/BackendStatusIndicator";

// ============================================================================
// useBackendHealth — convenience hook for graceful degradation
// Thin wrapper around BackendStatusIndicator's shared polling context.
// Exposes isOnline / isDegraded semantics for feature-level gating.
// ============================================================================

export interface BackendHealthState {
  /** Backend is fully operational */
  isOnline: boolean;
  /** Backend is offline (consecutive failures detected) */
  isDegraded: boolean;
  /** Backend is recovering (just came back, transitional state) */
  isRecovering: boolean;
  /** Summary status */
  status: "online" | "offline" | "recovering";
  /** Timestamp of last health check attempt */
  lastCheck: number | null;
  /** Trigger an immediate health check */
  checkHealth: () => Promise<boolean>;
}

/**
 * useBackendHealth — convenience wrapper around useBackendStatusContext.
 *
 * Adds `isOnline` / `isDegraded` booleans and `lastCheck` timestamp
 * for simpler consumption in feature gating (e.g. read-only mode).
 *
 * Shares the single polling instance from BackendStatusProvider — does
 * NOT create a duplicate polling loop.
 *
 * @example
 * ```tsx
 * const { isOnline, isDegraded } = useBackendHealth();
 * if (isDegraded) return <DegradationBanner />;
 * ```
 */
export function useBackendHealth(): BackendHealthState {
  const { status, isPolling, checkHealth } = useBackendStatusContext();

  return {
    isOnline: status === "online",
    isDegraded: status === "offline",
    isRecovering: status === "recovering",
    status,
    lastCheck: isPolling ? Date.now() : null,
    checkHealth,
  };
}
