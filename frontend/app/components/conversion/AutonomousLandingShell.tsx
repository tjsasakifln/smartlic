'use client';

/**
 * AutonomousLandingShell — CONV-010-2 (#1509)
 *
 * A wrapper component that converts entity pages into autonomous landing pages.
 * Composes three slots:
 *   1. headline -> ValuePropositionAboveFold (hero banner)
 *   2. insight-cards -> AhaMomentPanel (insight grid)
 *   3. cta-block -> CTAContextual (CTA button)
 *
 * Fires Mixpanel event `landing_autonomous_view` on mount.
 *
 * Mobile responsive via Tailwind breakpoints.
 */

import React, { useEffect } from 'react';
import ValuePropositionAboveFold from './ValuePropositionAboveFold';
import AhaMomentPanel from './AhaMomentPanel';
import type { InsightCard } from './AhaMomentPanel';
import CTAContextual from './CTAContextual';
import type { CTAVariant } from './CTAContextual';

export type EntityType =
  | 'fornecedor'
  | 'orgao'
  | 'cnpj'
  | 'setor'
  | 'municipio'
  | 'contrato';

export interface AutonomousLandingShellProps {
  /** Entity type driving template selection */
  entityType: EntityType;
  /** Entity name for personalization */
  entityName: string;
  /** Entity-specific data used for proposal generation */
  entityData: Record<string, unknown>;
  /** Value proposition text */
  valueProp: string;
  /** Supporting detail (optional) */
  supportingDetail?: string;
  /** Insights for AhaMomentPanel */
  insights: Array<{
    label: string;
    value: string;
    subtext?: string;
    icon?: 'chart' | 'money' | 'building' | 'target';
  }>;
  /** CTA variant */
  ctaVariant: CTAVariant;
  /** Override CTA text */
  ctaText?: string;
}

/**
 * AutonomousLandingShell
 *
 * Converts any entity page into an autonomous landing page by composing
 * ValuePropositionAboveFold, AhaMomentPanel, and CTAContextual.
 *
 * @example
 * <AutonomousLandingShell
 *   entityType="fornecedor"
 *   entityName="Empresa ABC Ltda"
 *   entityData={{ total_contratos: 42 }}
 *   valueProp="Análise concorrencial com inteligência artificial"
 *   insights={[{ label: "Contratos", value: "42", icon: "chart" }]}
 *   ctaVariant="trial"
 * />
 */
export default function AutonomousLandingShell({
  entityType,
  entityName,
  entityData,
  valueProp,
  supportingDetail,
  insights,
  ctaVariant,
  ctaText,
}: AutonomousLandingShellProps) {
  // Fire Mixpanel event on mount
  useEffect(() => {
    if (typeof window !== 'undefined' && window.mixpanel) {
      window.mixpanel.track('landing_autonomous_view', {
        entityType,
        entityName,
      });
    }
  }, [entityType, entityName]);

  return (
    <main aria-label={`Página autônoma — ${entityName}`} className="min-h-screen">
      {/* Headline slot: ValuePropositionAboveFold */}
      <ValuePropositionAboveFold
        entityType={entityType}
        entityName={entityName}
        valueProp={valueProp}
        supportingDetail={supportingDetail}
      />

      {/* Content container for insight-cards and cta-block */}
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6 sm:py-12">
        {/* Insight-cards slot: AhaMomentPanel */}
        <AhaMomentPanel
          entityType={entityType}
          insights={insights}
        />

        {/* Spacer before CTA */}
        <div className="my-8 border-t border-gray-100" />

        {/* CTA-block slot: CTAContextual */}
        <CTAContextual
          variant={ctaVariant}
          entityType={entityType}
          entityName={entityName}
          ctaText={ctaText}
        />
      </div>
    </main>
  );
}
