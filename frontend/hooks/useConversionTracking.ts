/**
 * CONV-009 (#1318): useConversionTracking hook.
 *
 * React hook that automatically tracks:
 *   - Scroll depth milestones (25%, 50%, 75%, 100%)
 *   - Time-on-page milestones (30s, 60s, 120s)
 *   - CTA view events (via IntersectionObserver)
 *
 * All events use the standardized ConversionContext params for downstream
 * attribution (source_template, entity_id, setor, uf, intent_cluster).
 *
 * Import pattern:
 *   import { useConversionTracking } from '@/hooks/useConversionTracking';
 */

'use client';

import { useEffect, useRef, useCallback } from 'react';
import {
  trackPageScroll,
  trackTimeOnPage,
  trackCTAView,
  type ConversionContext,
} from '@/lib/analytics/conversion-tracker';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UseConversionTrackingOptions extends ConversionContext {
  /** Enable or disable tracking (default: true) */
  enabled?: boolean;
  /** Additional custom properties to include in every event */
  extraProps?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// useScrollTracker
// ---------------------------------------------------------------------------

type ScrollTrackerOptions = UseConversionTrackingOptions;

/**
 * Track scroll depth at configurable thresholds.
 *
 * Fires at 25%, 50%, 75%, and 100% scroll depth. Each threshold fires at
 * most once per component mount via a ref guard.
 */
export function useScrollTracker(options: ScrollTrackerOptions): void {
  const { enabled = true, extraProps, ...context } = options;
  const firedRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return;

    firedRef.current.clear();

    const handleScroll = () => {
      const scrollTop = window.scrollY;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;

      if (docHeight <= 0) return;

      const percent = Math.min(100, Math.round((scrollTop / docHeight) * 100));

      const thresholds = [25, 50, 75, 100];
      for (const threshold of thresholds) {
        if (percent >= threshold && !firedRef.current.has(threshold)) {
          firedRef.current.add(threshold);
          trackPageScroll({
            ...context,
            ...extraProps,
            depth: threshold as 25 | 50 | 75 | 100,
            page_height: document.documentElement.scrollHeight,
            viewport_height: window.innerHeight,
          });
        }
      }
    };

    // Debounce scroll handler for performance
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

    window.addEventListener('scroll', onScroll, { passive: true });

    // Check initial scroll position immediately
    handleScroll();

    return () => {
      window.removeEventListener('scroll', onScroll);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, context.source_template, context.entity_id, context.setor, context.uf, context.intent_cluster]);
}

// ---------------------------------------------------------------------------
// useTimeOnPageTracker
// ---------------------------------------------------------------------------

type TimeOnPageOptions = UseConversionTrackingOptions;

/**
 * Track time spent on page at configurable intervals.
 *
 * Fires at 30s, 60s, and 120s after component mount. Each interval fires at
 * most once per mount via a ref guard.
 */
export function useTimeOnPageTracker(options: TimeOnPageOptions): void {
  const { enabled = true, extraProps, ...context } = options;
  const firedRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return;

    firedRef.current.clear();

    const intervals = [
      { seconds: 30, delay: 30_000 },
      { seconds: 60, delay: 60_000 },
      { seconds: 120, delay: 120_000 },
    ];

    const timers: ReturnType<typeof setTimeout>[] = [];

    for (const { seconds, delay } of intervals) {
      const timer = setTimeout(() => {
        if (!firedRef.current.has(seconds)) {
          firedRef.current.add(seconds);
          trackTimeOnPage({
            ...context,
            ...extraProps,
            seconds,
          });
        }
      }, delay);
      timers.push(timer);
    }

    return () => {
      timers.forEach(clearTimeout);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, context.source_template, context.entity_id, context.setor, context.uf, context.intent_cluster]);
}

// ---------------------------------------------------------------------------
// useElementViewTracker
// ---------------------------------------------------------------------------

export interface ElementViewTrackerOptions extends UseConversionTrackingOptions {
  /** CSS selector or ref-based element to observe */
  elementSelector?: string;
  /** IntersectionObserver threshold (default: 0.5 = 50% visible) */
  threshold?: number;
  /** Unique CTA identifier */
  cta_id?: string;
  /** CTA position on page */
  cta_position?: string;
  /** CTA variant */
  cta_variant?: string;
  /** Disable tracking after first view (default: true) */
  trackOnce?: boolean;
}

/**
 * Track when an element (e.g. a CTA) becomes visible in the viewport.
 *
 * Uses IntersectionObserver to fire a `cta_view` event when the element
 * reaches the configured visibility threshold.
 *
 * @example
 * ```tsx
 * useElementViewTracker({
 *   elementSelector: '#hero-cta',
 *   cta_id: 'hero-cta',
 *   cta_position: 'hero',
 *   source_template: 'fornecedor_page',
 *   setor: 'pavimentacao-asfaltica',
 * });
 * ```
 */
export function useElementViewTracker(options: ElementViewTrackerOptions): void {
  const {
    enabled = true,
    extraProps,
    elementSelector,
    threshold = 0.5,
    cta_id,
    cta_position,
    cta_variant,
    trackOnce = true,
    ...context
  } = options;

  const hasFiredRef = useRef(false);

  useEffect(() => {
    if (!enabled || typeof window === 'undefined') return;
    if (!elementSelector) return;
    if (trackOnce && hasFiredRef.current) return;

    const element = document.querySelector(elementSelector);
    if (!element) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            if (trackOnce && hasFiredRef.current) return;
            hasFiredRef.current = true;

            trackCTAView({
              ...context,
              ...extraProps,
              cta_id: cta_id ?? elementSelector,
              cta_position: cta_position ?? 'unknown',
              cta_variant,
            });

            if (trackOnce) {
              observer.disconnect();
            }
          }
        }
      },
      { threshold },
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, elementSelector, threshold, cta_id, cta_position, cta_variant, trackOnce]);
}

// ---------------------------------------------------------------------------
// useConversionTracking (composite hook)
// ---------------------------------------------------------------------------

export interface ConversionTrackingConfig extends UseConversionTrackingOptions {
  /** Track scroll depth milestones (default: true) */
  trackScroll?: boolean;
  /** Track time-on-page milestones (default: true) */
  trackTime?: boolean;
}

/**
 * Composite hook that activates all conversion tracking for a page.
 *
 * Automatically tracks scroll depth (25/50/75/100%), time-on-page
 * (30s/60s/120s), and returns helper functions for manual event tracking.
 *
 * @example
 * ```tsx
 * const { trackCTAClick } = useConversionTracking({
 *   source_template: 'fornecedor_page',
 *   entity_id: '12345678000100',
 *   setor: 'pavimentacao-asfaltica',
 *   uf: 'SC',
 *   intent_cluster: 'fornecedor',
 * });
 *
 * // Manual CTA click tracking
 * <button onClick={() => trackCTAClick({
 *   cta_id: 'hero-cta',
 *   cta_position: 'hero',
 * })}>Click me</button>
 * ```
 */
export function useConversionTracking(options: ConversionTrackingConfig) {
  const { trackScroll = true, trackTime = true, enabled = true, ...rest } = options;

  // Auto-track scroll depth
  useScrollTracker({
    ...rest,
    enabled: enabled && trackScroll,
  });

  // Auto-track time on page
  useTimeOnPageTracker({
    ...rest,
    enabled: enabled && trackTime,
  });

  /**
   * Manually track a CTA click event with the current context pre-filled.
   */
  const trackCTAClick = useCallback(
    (event: {
      cta_id: string;
      cta_position: string;
      cta_variant?: string;
      cta_destination?: string;
      cta_label?: string;
      extraProps?: Record<string, unknown>;
    }) => {
      if (!enabled) return;
      // Dynamic import to avoid circular deps with the static import above
      void import('@/lib/analytics/conversion-tracker').then((mod) => {
        mod.trackCTAClick({
          source_template: rest.source_template,
          entity_id: rest.entity_id,
          setor: rest.setor,
          uf: rest.uf,
          intent_cluster: rest.intent_cluster,
          ...event.extraProps,
          cta_id: event.cta_id,
          cta_position: event.cta_position,
          cta_variant: event.cta_variant,
          cta_destination: event.cta_destination,
          cta_label: event.cta_label,
        });
      });
    },
    [enabled, rest.source_template, rest.entity_id, rest.setor, rest.uf, rest.intent_cluster],
  );

  return {
    trackCTAClick,
  };
}
