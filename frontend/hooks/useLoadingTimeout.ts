"use client";

/**
 * useLoadingTimeout — Hook for handling indefinite loading states.
 *
 * UX-309: Fires after a configurable timeout (default 30s) and provides
 * timedOut flag, reset function, and remaining time. Prevents loading
 * states like "Aguardando..." from hanging forever without user feedback.
 *
 * @example
 * ```tsx
 * const { timedOut, reset } = useLoadingTimeout({
 *   timeoutMs: 30000,
 *   enabled: isLoading,
 * });
 *
 * if (timedOut) {
 *   return <TimeoutFallback onRetry={reset} />;
 * }
 * ```
 */

import { useState, useEffect, useCallback, useRef } from "react";

export interface UseLoadingTimeoutOptions {
  /** Timeout in milliseconds (default: 30000 = 30s) */
  timeoutMs?: number;
  /** Whether the timeout should be active (default: true) */
  enabled?: boolean;
  /** Callback fired when timeout is reached */
  onTimeout?: () => void;
}

export interface UseLoadingTimeoutReturn {
  /** Whether the timeout has been reached */
  timedOut: boolean;
  /** Reset the timeout counter (call when retrying or data arrives) */
  reset: () => void;
  /** Time remaining in milliseconds (0 when timed out) */
  timeLeft: number;
}

export function useLoadingTimeout({
  timeoutMs = 30000,
  enabled = true,
  onTimeout,
}: UseLoadingTimeoutOptions = {}): UseLoadingTimeoutReturn {
  const [timedOut, setTimedOut] = useState(false);
  const [timeLeft, setTimeLeft] = useState(timeoutMs);
  const onTimeoutRef = useRef(onTimeout);
  const startTimeRef = useRef<number>(Date.now());

  // Keep callback ref fresh without re-triggering the effect
  useEffect(() => {
    onTimeoutRef.current = onTimeout;
  }, [onTimeout]);

  const reset = useCallback(() => {
    setTimedOut(false);
    setTimeLeft(timeoutMs);
    startTimeRef.current = Date.now();
  }, [timeoutMs]);

  useEffect(() => {
    if (!enabled) {
      // When disabled, reset to initial state (e.g., loading finished)
      setTimedOut(false);
      setTimeLeft(timeoutMs);
      return;
    }

    // Reset state on each fresh enable
    setTimedOut(false);
    setTimeLeft(timeoutMs);
    startTimeRef.current = Date.now();

    const interval = setInterval(() => {
      const elapsed = Date.now() - startTimeRef.current;
      const remaining = Math.max(0, timeoutMs - elapsed);
      setTimeLeft(remaining);

      if (remaining <= 0) {
        clearInterval(interval);
        setTimedOut(true);
        onTimeoutRef.current?.();
      }
    }, 1000);

    return () => {
      clearInterval(interval);
    };
  }, [timeoutMs, enabled]);

  return { timedOut, reset, timeLeft };
}
