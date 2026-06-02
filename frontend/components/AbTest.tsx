/**
 * A/B Testing React Component for pSEO pages.
 * CONV-012 (#1323).
 *
 * Renders the correct variant based on cookie assignment and tracks
 * impression via Mixpanel on mount.
 *
 * === SSR Behavior ===
 * On the server, this component returns null. Variant assignment and
 * rendering happen only on the client (after hydration). This prevents
 * layout shifts and ensures cookie consistency.
 *
 * === Usage ===
 *
 * ```tsx
 * <AbTest
 *   experimentId="pseo-cta-v1"
 *   variants={{
 *     control: <CurrentCTASection />,
 *     variant_a: <AlternativeCTASection />,
 *   }}
 * />
 * ```
 *
 * === Props ===
 * - experimentId: Unique identifier for the experiment
 * - variants: Record mapping variant names to their React nodes
 * - fallback: Optional React node to render when something goes wrong
 *   (defaults to the first variant)
 */

'use client';

import { useEffect, useState } from 'react';
import {
  getOrSetVariant,
  trackExperimentImpression,
} from '@/lib/ab-testing';
import type { VariantsMap } from '@/lib/ab-testing';

export interface AbTestProps {
  /** Unique experiment identifier (e.g. "pseo-cta-v1"). */
  experimentId: string;

  /**
   * Map of variant names to their rendered content.
   * Must have at least one entry.
   * Example: { control: <div>A</div>, variant_a: <div>B</div> }
   */
  variants: VariantsMap;

  /**
   * Optional fallback content to render if no valid variant is found.
   * Defaults to rendering the first variant in the map.
   */
  fallback?: React.ReactNode;
}

/**
 * Client-only A/B test component that renders the correct variant
 * for the current user based on cookie assignment.
 *
 * - On SSR: returns null (renders nothing on the server).
 * - On first client render: assigns variant and renders it.
 * - Tracks impression once on mount via Mixpanel.
 */
export function AbTest({
  experimentId,
  variants,
  fallback,
}: AbTestProps): React.ReactNode {
  const [variant, setVariant] = useState<string | null>(null);
  const [impressionTracked, setImpressionTracked] = useState(false);

  // Assign variant on mount (client-side only)
  useEffect(() => {
    const variantNames = Object.keys(variants);

    if (variantNames.length === 0) {
      setVariant('__empty__');
      return;
    }

    const assigned = getOrSetVariant(experimentId, variantNames);
    setVariant(assigned);
  }, [experimentId, variants]);

  // Track impression on mount (only once)
  useEffect(() => {
    if (impressionTracked) return;
    if (variant === null || variant === '__empty__') return;

    setImpressionTracked(true);
    trackExperimentImpression(experimentId, variant);
  }, [experimentId, variant, impressionTracked]);

  // SSR: render nothing to avoid hydration mismatch
  if (variant === null) {
    return null;
  }

  // Empty variants map
  if (variant === '__empty__') {
    return fallback ?? null;
  }

  // Variant not found in map — use fallback or first variant
  const variantContent = variants[variant];
  if (variantContent === undefined) {
    const firstKey = Object.keys(variants)[0];
    if (firstKey && variants[firstKey] !== undefined) {
      return <>{variants[firstKey]}</>;
    }
    return fallback ?? null;
  }

  return <>{variantContent}</>;
}
