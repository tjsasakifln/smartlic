/**
 * Time-on-page engagement tracking hook for pSEO pages.
 * CONV-009b (#1325).
 *
 * Fires pseo_engagement with time_on_page_ms on:
 *   - visibilitychange (when page becomes hidden)
 *   - beforeunload (when user navigates away)
 *
 * Fires at most once per page load (first trigger wins).
 * SSR-safe: no-op when window is unavailable.
 * Never throws — errors are swallowed silently.
 */

'use client';

import { useEffect, useRef } from 'react';
import { trackPseoEvent, PseoSourceTemplate } from './pseo';

export interface EngagementConfig {
  sourceTemplate: PseoSourceTemplate;
  entityId?: string;
  setor?: string;
  uf?: string;
}

/** Minimum time-on-page in ms to consider meaningful (1s). */
const MIN_MEANINGFUL_MS = 1_000;

/**
 * Track time spent on page. Fires `pseo_engagement` once when the user
 * leaves the page or the tab becomes hidden. Avoids firing for trivial
 * bounces (<1s).
 */
export function useEngagement(config: EngagementConfig): void {
  const startTimeRef = useRef<number>(0);
  const firedRef = useRef(false);

  useEffect(() => {
    startTimeRef.current = Date.now();
    firedRef.current = false;

    const fireEngagement = () => {
      if (firedRef.current) return;
      const elapsed = Date.now() - startTimeRef.current;
      if (elapsed < MIN_MEANINGFUL_MS) return;

      firedRef.current = true;
      trackPseoEvent('pseo_engagement', {
        source_template: config.sourceTemplate,
        time_on_page_ms: elapsed,
        entity_id: config.entityId,
        setor: config.setor,
        uf: config.uf,
      });
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        fireEngagement();
      }
    };

    window.addEventListener('beforeunload', fireEngagement);
    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      window.removeEventListener('beforeunload', fireEngagement);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      // Fire on unmount if user navigates within the SPA
      fireEngagement();
    };
  }, [config.sourceTemplate, config.entityId, config.setor, config.uf]);
}
