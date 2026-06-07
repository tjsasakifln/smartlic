'use client';

import Link from 'next/link';
import { useIntentDetection, type IntentCluster } from './IntentRouter';
import { CLUSTER_LABELS } from './intent-keywords';

/**
 * Secondary action descriptor (link text + href).
 */
export interface SecondaryAction {
  text: string;
  href: string;
}

/**
 * Offer data per intent cluster.
 */
interface ClusterOffer {
  headline: string;
  offer: string;
  ctaText: string;
  ctaLink: string;
  secondaryAction: SecondaryAction;
}

/**
 * Props for the IntentTrail wrapper component.
 *
 * When `cluster` is provided, auto-detection is skipped entirely and the
 * specified cluster content is rendered. When omitted, the component uses
 * `useIntentDetection()` to detect the cluster from the current page context
 * (URL params, referrer, and/or searchTerm).
 *
 * Any prop can be overridden individually — the override takes precedence
 * over the cluster-specific default.
 */
export interface IntentTrailProps {
  /** Explicit cluster — skips auto-detection when provided */
  cluster?: IntentCluster;
  /** Search term for auto-detection (ignored when cluster is explicit) */
  searchTerm?: string;
  /** Custom headline override */
  headline?: string;
  /** Custom offer text override */
  offer?: string;
  /** Custom CTA text override */
  ctaText?: string;
  /** Custom CTA link override */
  ctaLink?: string;
  /** Custom secondary action override */
  secondaryAction?: SecondaryAction;
}

/**
 * Default cluster-specific offers and CTAs for the conversion trail.
 */
const CLUSTER_OFFERS: Record<IntentCluster, ClusterOffer> = {
  comercial: {
    headline: 'Venda para o governo com inteligência',
    offer:
      'Descubra editais classificados por setor com análise de viabilidade. Aumente suas chances de vencer licitações.',
    ctaText: 'Começar trial grátis →',
    ctaLink: '/signup?source=intent-comercial',
    secondaryAction: {
      text: 'Ver exemplos de resultados →',
      href: '/buscar',
    },
  },
  investigativa: {
    headline: 'Pesquise licitações com profundidade',
    offer:
      'Analise histórico de concorrências, compare preços e mapeie tendências do mercado público com dados reais.',
    ctaText: 'Começar trial grátis →',
    ctaLink: '/signup?source=intent-investigativa',
    secondaryAction: {
      text: 'Explorar dados abertos →',
      href: '/observatorio',
    },
  },
  juridica: {
    headline: 'Fundamentação jurídica para licitações',
    offer:
      'Acesse editais completos, jurisprudência e análise detalhada para embasar seus recursos e impugnações.',
    ctaText: 'Começar trial grátis →',
    ctaLink: '/signup?source=intent-juridica',
    secondaryAction: {
      text: 'Ver base legal →',
      href: '/compliance',
    },
  },
  subcontratacao: {
    headline: 'Encontre parceiros de licitação',
    offer:
      'Identifique consórcios, subcontratações e oportunidades para sua empresa atuar como fornecedor terceiro.',
    ctaText: 'Começar trial grátis →',
    ctaLink: '/signup?source=intent-subcontratacao',
    secondaryAction: {
      text: 'Ver editais recentes →',
      href: '/licitacoes',
    },
  },
  geral: {
    headline: 'Inteligência em licitações públicas',
    offer:
      'Plataforma completa para descobrir, analisar e ganhar licitações. IA classificando por setor automaticamente.',
    ctaText: 'Começar trial grátis →',
    ctaLink: '/signup?source=intent-geral',
    secondaryAction: {
      text: 'Conhecer funcionalidades →',
      href: '/features',
    },
  },
};

/**
 * IntentTrail — wrapper component that renders a segment-specific offer,
 * CTA, and journey based on the detected intent cluster.
 *
 * Integrates with IntentRouter for automatic intent detection. Can also be
 * used with an explicit cluster or with individual prop overrides.
 *
 * @example
 * ```tsx
 * // Auto-detect from page context
 * <IntentTrail />
 *
 * // Explicit cluster
 * <IntentTrail cluster="comercial" />
 *
 * // Auto-detect with custom headline
 * <IntentTrail searchTerm="vender para prefeitura" headline="Título customizado" />
 * ```
 */
export default function IntentTrail({
  cluster: explicitCluster,
  searchTerm,
  headline: headlineOverride,
  offer: offerOverride,
  ctaText: ctaTextOverride,
  ctaLink: ctaLinkOverride,
  secondaryAction: secondaryActionOverride,
}: IntentTrailProps) {
  const detected = useIntentDetection(searchTerm);
  const cluster = explicitCluster ?? detected.cluster;
  const content = CLUSTER_OFFERS[cluster];

  const headline = headlineOverride ?? content.headline;
  const offer = offerOverride ?? content.offer;
  const ctaText = ctaTextOverride ?? content.ctaText;
  const ctaLink = ctaLinkOverride ?? content.ctaLink;
  const secondary = secondaryActionOverride ?? content.secondaryAction;

  return (
    <section
      aria-label={`Oferta ${CLUSTER_LABELS[cluster]}`}
      className="my-10 rounded-xl border border-blue-200 bg-blue-50 p-6 text-center sm:p-8"
    >
      <h2 className="text-xl font-bold text-gray-900 sm:text-2xl">{headline}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm text-gray-600 sm:text-base">{offer}</p>

      <Link
        href={ctaLink}
        className="mt-5 inline-block rounded-xl bg-green-600 px-8 py-3 text-center font-bold text-white shadow-lg transition-colors hover:bg-green-700 sm:w-auto"
      >
        {ctaText}
      </Link>

      {secondary && (
        <div className="mt-3">
          <Link
            href={secondary.href}
            className="text-sm font-medium text-blue-600 underline underline-offset-2 transition-colors hover:text-blue-800"
          >
            {secondary.text}
          </Link>
        </div>
      )}
    </section>
  );
}
