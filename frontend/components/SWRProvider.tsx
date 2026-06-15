"use client";

import { SWRConfig } from "swr";
import { fetcher } from "../lib/fetcher";

/**
 * TD-008 AC1: Global SWR config provider.
 * - revalidateOnFocus disabled (avoid unnecessary API calls on tab switch)
 * - dedupingInterval 5s (prevent duplicate concurrent requests)
 * - errorRetryCount 3 (built-in retry with exponential backoff)
 * - errorRetryInterval 5s (backoff between retries — ISSUE-1791 graceful degradation)
 *
 * Graceful degradation behavior (ISSUE-1791):
 * SWR keeps serving stale (cached) data when revalidation fails.
 * This means if the backend goes DOWN, pages that have previously loaded
 * data via SWR will continue to display that data while retrying in the
 * background. Combined with DegradationBanner, users see stale data +
 * a visual indicator rather than a white screen or error flash.
 */
export function SWRProvider({ children }: { children: React.ReactNode }) {
  return (
    <SWRConfig
      value={{
        fetcher,
        revalidateOnFocus: false,
        dedupingInterval: 5000,
        errorRetryCount: 3,
        errorRetryInterval: 5000,
      }}
    >
      {children}
    </SWRConfig>
  );
}
