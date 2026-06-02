/**
 * Scroll depth tracking hook for pSEO pages.
 * CONV-009b (#1325).
 *
 * Fires pseo_scroll_depth at 25%, 50%, 75%, and 100% scroll milestones.
 * Each milestone fires at most once per page load.
 * SSR-safe: no-op when window is unavailable.
 * Never throws — errors are swallowed silently.
 */

'use client';

import { useEffect, useRef, useCallback } from 'react';
import { trackPseoEvent, PseoSourceTemplate } from './pseo';

export interface ScrollDepthConfig {
  sourceTemplate: PseoSourceTemplate;
  entityId?: string;
  setor?: string;
  uf?: string;
}

const MILESTONES: readonly number[] = [25, 50, 75, 100];

/**
 * Track page scroll depth milestones via requestAnimationFrame-throttled
 * scroll handler. Fires `pseo_scroll_depth` once per threshold.
 */
export function useScrollDepth(config: ScrollDepthConfig): void {
  const firedRef = useRef<Set<number>>(new Set());
  const configRef = useRef(config);

  // Keep config ref current without triggering effect re-run
  configRef.current = config;

  const handleScroll = useCallback(() => {
    const scrollTop = window.scrollY;
    const docHeight = document.documentElement.scrollHeight - window.innerHeight;
    if (docHeight <= 0) return;

    const percent = Math.min(100, Math.round((scrollTop / docHeight) * 100));

    for (const milestone of MILESTONES) {
      if (percent >= milestone && !firedRef.current.has(milestone)) {
        firedRef.current.add(milestone);
        const cfg = configRef.current;
        trackPseoEvent('pseo_scroll_depth', {
          source_template: cfg.sourceTemplate,
          depth_percent: milestone,
          entity_id: cfg.entityId,
          setor: cfg.setor,
          uf: cfg.uf,
        });
      }
    }
  }, []);

  useEffect(() => {
    // Reset fired set on mount (new page load)
    firedRef.current = new Set();

    let ticking = false;
    const onScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          handleScroll();
          ticking = false;
        });
        ticking = true;
      }
    };

    // Check initial scroll position (user may already have scrolled)
    handleScroll();

    window.addEventListener('scroll', onScroll, { passive: true });

    return () => {
      window.removeEventListener('scroll', onScroll);
    };
  }, [handleScroll]);
}
