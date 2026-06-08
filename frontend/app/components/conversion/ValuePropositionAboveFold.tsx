'use client';

/**
 * ValuePropositionAboveFold — CONV-001
 *
 * Hero-section component that sits above the fold on entity pages.
 * Renders a gradient banner (brand-navy to brand-blue) with a personalized
 * headline based on entity type, value proposition text, and optional
 * supporting detail line.
 *
 * Responsive: full-width on mobile, max-width centered on desktop.
 */

import React from 'react';

export type EntityType =
  | 'fornecedor'
  | 'orgao'
  | 'cnpj'
  | 'setor'
  | 'municipio'
  | 'contrato';

export interface ValuePropositionAboveFoldProps {
  /** Page entity type */
  entityType: EntityType;
  /** Entity name to personalize the headline */
  entityName: string;
  /** Specific value proposition text */
  valueProp: string;
  /** Supporting detail line */
  supportingDetail?: string;
}

const HEADLINES: Record<EntityType, string> = {
  fornecedor: 'Quer vencer mais licitações como {name}?',
  orgao: 'Quer vender para {name}?',
  cnpj: 'Quer vencer mais licitações como {name}?',
  setor: 'Oportunidades no setor — {name}',
  municipio: 'Licitações em {name} — acompanhe em tempo real',
  contrato: 'Análise completa do contrato — {name}',
};

function interpolateHeadline(entityType: EntityType, entityName: string): string {
  const template = HEADLINES[entityType];
  return template.replace('{name}', entityName);
}

export default function ValuePropositionAboveFold({
  entityType,
  entityName,
  valueProp,
  supportingDetail,
}: ValuePropositionAboveFoldProps) {
  const headline = interpolateHeadline(entityType, entityName);

  return (
    <section
      aria-label="Proposta de valor"
      className="bg-gradient-to-br from-brand-navy to-brand-blue"
    >
      <div className="mx-auto flex max-w-landing flex-col items-center px-4 py-16 text-center text-white sm:px-6 sm:py-24">
        <h1 className="text-hero font-display font-extrabold leading-tight tracking-tighter">
          {headline}
        </h1>
        <p className="mt-4 max-w-2xl text-body-lg text-blue-100">
          {valueProp}
        </p>
        {supportingDetail && (
          <p className="mt-3 max-w-xl text-sm text-blue-200 sm:text-base">
            {supportingDetail}
          </p>
        )}
      </div>
    </section>
  );
}
