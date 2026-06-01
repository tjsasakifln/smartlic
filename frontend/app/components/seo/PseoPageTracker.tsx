/**
 * Renderless client component that wires pSEO analytics events for a page.
 * CONV-009b (#1325).
 *
 * Fires the specified view event on mount, plus manages scroll depth and
 * engagement tracking for the page lifecycle.
 *
 * Usage (in any server component):
 *   <PseoPageTracker
 *     sourceTemplate="licitacoes_hub"
 *     entityId={setor}
 *     setor={setor}
 *     viewEventName="pseo_edital_viewed"
 *   />
 *
 * Zero breaking change — renders null, does not affect layout or styling.
 */

'use client';

import { useEffect, useRef } from 'react';
import { trackPseoEvent, PseoEventName, PseoSourceTemplate } from '@/lib/analytics/pseo';
import { useScrollDepth } from '@/lib/analytics/useScrollDepth';
import { useEngagement } from '@/lib/analytics/useEngagement';

export interface PseoPageTrackerProps {
  /** Template identifier for attribution in Mixpanel dashboards. */
  sourceTemplate: PseoSourceTemplate;
  /** Entity identifier (CNPJ, sector slug, etc.). */
  entityId?: string;
  /** Sector slug (e.g. 'pavimentacao-asfaltica'). */
  setor?: string;
  /** Two-letter UF code (e.g. 'SC'). */
  uf?: string;
  /**
   * Optional view event to fire once on page mount.
   * Omit when the view event is already fired by another component
   * (e.g. fornecedor_page where FornecedorPseoCTA fires pseo_supplier_viewed).
   */
  viewEventName?: PseoEventName;
}

/**
 * Renderless tracker — fires pSEO analytics events based on page context.
 * Handles scroll depth, time-on-page, and optional view event.
 */
export function PseoPageTracker({
  sourceTemplate,
  entityId,
  setor,
  uf,
  viewEventName,
}: PseoPageTrackerProps): null {
  // Scroll depth tracking (25%, 50%, 75%, 100%)
  useScrollDepth({ sourceTemplate, entityId, setor, uf });

  // Time-on-page engagement tracking
  useEngagement({ sourceTemplate, entityId, setor, uf });

  // Fire page view event on mount (only once)
  const viewFiredRef = useRef(false);

  useEffect(() => {
    if (viewEventName && !viewFiredRef.current) {
      viewFiredRef.current = true;
      trackPseoEvent(viewEventName, {
        source_template: sourceTemplate,
        entity_id: entityId,
        setor,
        uf,
        page_url: typeof window !== 'undefined' ? window.location.href : undefined,
      });
    }
  }, [sourceTemplate, entityId, setor, uf, viewEventName]);

  return null;
}
