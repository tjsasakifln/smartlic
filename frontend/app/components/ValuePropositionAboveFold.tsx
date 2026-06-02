"use client";
/**
 * ValuePropositionAboveFold — CONV-001 (#1310)
 *
 * Caixa de valor agressiva acima da dobra para páginas pSEO informacionais.
 * Responde "como ganho dinheiro com isso?" em vez de "o que é isso?".
 *
 * Compartilha o contrato CtaConfig com CONV-004 (AhaMomentPanel) e dispara
 * os mesmos eventos Mixpanel: value_prop_view, value_cta_click.
 *
 * Props:
 *   pageType: CtaPageType — qual template está renderizando
 *   context: CtaContext — contexto dinâmico da página (slug, setor, uf, etc.)
 *   insightCards: InsightCard[] — 3 cards com dados reais do segmento
 *   headline?: string — headline customizada (fallback automático via cta-intent)
 *   subtext?: string — subtexto customizado (fallback automático via cta-intent)
 */

import { useEffect, useRef } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { getCtaByIntent } from "@/lib/cta-intent";
import type { CtaPageType, CtaContext } from "@/lib/cta-intent";
import { trackValuePropView, trackValuePropCtaClick } from "@/lib/analytics-events";
import type { ValuePropViewEvent, ValuePropCtaClickEvent } from "@/lib/analytics-events";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface InsightCard {
  /** Ícone/emoji representando o card */
  icon: string;
  /** Título curto do card (ex: "R$ 2,5 Mi em contratos") */
  title: string;
  /** Descrição contextual (ex: "Valor médio por edital no setor de TI") */
  description: string;
}

export interface ValuePropositionAboveFoldProps {
  /** Tipo de página para derivar headline e CTA */
  pageType: CtaPageType;
  /** Contexto dinâmico da página */
  context: CtaContext;
  /** 3 cards de insight com dados reais do segmento */
  insightCards: [InsightCard, InsightCard, InsightCard];
  /** Headline customizada (opcional — fallback via cta-intent) */
  headline?: string;
  /** Subtexto customizado (opcional — fallback via cta-intent) */
  subtext?: string;
  /** Blur preview text (ex: "há 47 órgãos comprando isso na sua região") */
  blurPreview?: string;
}

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.12 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4 },
  },
};

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function ValuePropositionAboveFold({
  pageType,
  context,
  insightCards,
  headline,
  subtext,
  blurPreview,
}: ValuePropositionAboveFoldProps) {
  const trackedRef = useRef(false);
  const ctaConfig = getCtaByIntent(pageType, context);

  // Track view impression once on mount
  useEffect(() => {
    if (trackedRef.current) return;
    trackedRef.current = true;

    const event: ValuePropViewEvent = {
      page_type: pageType,
      slug: context.slug,
      headline: headline ?? ctaConfig.headline,
    };
    trackValuePropView(event);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCtaClick = (label: string) => {
    const event: ValuePropCtaClickEvent = {
      page_type: pageType,
      slug: context.slug,
      campaign: ctaConfig.campaign,
      cta_label: label,
    };
    trackValuePropCtaClick(event);
  };

  const displayHeadline = headline ?? ctaConfig.headline;
  const displaySubtext = subtext ?? ctaConfig.subtext;

  return (
    <motion.section
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="not-prose mb-8 sm:mb-10"
      aria-label="Oportunidades de receita"
      data-testid="value-proposition-above-fold"
    >
      {/* ── Headline + Subtext ── */}
      <motion.div
        variants={cardVariants}
        className="bg-gradient-to-br from-brand-navy to-brand-blue rounded-xl p-6 sm:p-8 text-white"
      >
        <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold mb-3 leading-tight">
          {displayHeadline}
        </h1>
        <p className="text-white/80 text-sm sm:text-base max-w-2xl leading-relaxed">
          {displaySubtext}
        </p>

        {/* ── Blur Preview ── */}
        {blurPreview && (
          <div className="mt-4 inline-flex items-center gap-2 rounded-lg bg-white/10 px-4 py-2 text-sm text-white/90">
            <span className="select-none blur-[1px]" aria-hidden="true">
              {blurPreview}
            </span>
            <span className="text-xs text-white/50">(faça login para ver os dados)</span>
          </div>
        )}

        {/* ── Primary CTA ── */}
        <div className="mt-5 flex flex-col sm:flex-row gap-3">
          <Link
            href={ctaConfig.buttonLink}
            className="inline-block bg-white text-brand-navy font-semibold px-6 py-3 rounded-button text-sm sm:text-base transition-all hover:scale-[1.02] active:scale-[0.98] text-center shadow-sm"
            onClick={() => handleCtaClick(ctaConfig.buttonText)}
            data-testid="value-prop-cta-primary"
          >
            {ctaConfig.buttonText}
          </Link>
          {ctaConfig.secondaryText && ctaConfig.secondaryLink && (
            <Link
              href={ctaConfig.secondaryLink}
              className="inline-block bg-white/10 hover:bg-white/20 border border-white/30 text-white font-medium px-6 py-3 rounded-button text-sm sm:text-base text-center transition-all"
              onClick={() => handleCtaClick(ctaConfig.secondaryText!)}
              data-testid="value-prop-cta-secondary"
            >
              {ctaConfig.secondaryText}
            </Link>
          )}
        </div>

        {/* ── Social Proof ── */}
        {ctaConfig.socialProof && (
          <p className="mt-3 text-xs text-white/60" data-testid="value-prop-social-proof">
            {ctaConfig.socialProof}
          </p>
        )}
      </motion.div>

      {/* ── 3 Insight Cards ── */}
      <motion.div
        variants={containerVariants}
        className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4 mt-4"
      >
        {insightCards.map((card, index) => (
          <motion.div
            key={index}
            variants={cardVariants}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-1)] p-4 hover:border-brand-blue/30 hover:shadow-sm transition-all"
            data-testid={`value-prop-card-${index}`}
          >
            <span className="text-2xl block mb-2" aria-hidden="true">
              {card.icon}
            </span>
            <p className="text-sm font-bold text-[var(--ink)] mb-1 leading-snug">
              {card.title}
            </p>
            <p className="text-xs text-[var(--ink-secondary)] leading-relaxed">
              {card.description}
            </p>
          </motion.div>
        ))}
      </motion.div>
    </motion.section>
  );
}
