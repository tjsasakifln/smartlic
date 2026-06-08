/**
 * AutonomousLandingShell (#1509, #1319)
 *
 * A wrapper/layout component that makes any entity page work as a standalone
 * landing page — without depending on main navigation context.
 *
 * REV-002 (Step 2 of EPIC-REV-ENTITY-MONETIZATION): Each entity page functions
 * as a mini-landing page with its own value proposition, social proof, and
 * conversion path.
 *
 * Features:
 *   - Page-specific title + description (SEO metadata)
 *   - Social proof section (configurable stats)
 *   - Trust signals (security badges, testimonial quote if available)
 *   - Clear CTA area
 *   - What-is-this-section (explains SmartLic briefly for first-time visitors)
 *   - Mobile-first, follows existing design tokens (Tailwind + CSS variables)
 */

import Link from 'next/link';
import type { ReactNode } from 'react';
import LandingNavbar from './landing/LandingNavbar';
import Footer from './Footer';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SocialProofItem {
  label: string;
  value: string;
}

export interface AutonomousLandingShellProps {
  /** Entity type for contextual messaging. */
  entityType: 'fornecedor' | 'orgao' | 'setor' | 'municipio' | 'contrato' | 'item';
  /** Human-readable entity name (e.g. "Empresa ABC Ltda"). */
  entityName: string;
  /** Optional short description of the entity. */
  entityDescription?: string;
  /** Main page content. */
  children: ReactNode;
  /** Optional custom CTA component to render in the CTA area. */
  ctaComponent?: ReactNode;
  /** Optional social proof items (e.g. [{ label: "Empresas", value: "500+" }]). */
  socialProof?: SocialProofItem[];
}

// ---------------------------------------------------------------------------
// Default social proof — used when caller doesn't provide custom data
// ---------------------------------------------------------------------------

const DEFAULT_SOCIAL_PROOF: SocialProofItem[] = [
  { label: 'Empresas cadastradas', value: '2.000+' },
  { label: 'Editais analisados', value: '50.000+' },
  { label: 'Fontes oficiais', value: '3' },
];

// ---------------------------------------------------------------------------
// Entity-type configuration
// ---------------------------------------------------------------------------

const ENTITY_CONFIG: Record<
  AutonomousLandingShellProps['entityType'],
  { ctaSuffix: string; whatIsDescription: string }
> = {
  fornecedor: {
    ctaSuffix: 'deste fornecedor',
    whatIsDescription:
      'O SmartLic consolida dados públicos de contratos e licitações para ajudar sua empresa a encontrar oportunidades com o governo.',
  },
  orgao: {
    ctaSuffix: 'deste órgão',
    whatIsDescription:
      'O SmartLic monitora editais públicos em tempo real para que você não perca nenhuma oportunidade de negócio com o governo.',
  },
  setor: {
    ctaSuffix: 'deste setor',
    whatIsDescription:
      'O SmartLic analisa licitações por setor de atuação, classificando editais por relevância para o seu negócio.',
  },
  municipio: {
    ctaSuffix: 'deste município',
    whatIsDescription:
      'O SmartLic agrega licitações municipais, estaduais e federais em um só lugar para facilitar sua prospecção.',
  },
  contrato: {
    ctaSuffix: 'deste contrato',
    whatIsDescription:
      'O SmartLic oferece inteligência sobre contratos públicos para ajudar sua empresa a entender o mercado B2G.',
  },
  item: {
    ctaSuffix: 'deste item',
    whatIsDescription:
      'O SmartLic identifica itens e serviços comprados pelo governo para mapear oportunidades para o seu negócio.',
  },
};

// ---------------------------------------------------------------------------
// Trust signals
// ---------------------------------------------------------------------------

const TRUST_SIGNALS = [
  { icon: '🔒', label: 'Dados oficiais', description: 'Fontes governamentais (PNCP, ComprasGov, PCP)' },
  { icon: '🤖', label: 'Classificação por IA', description: 'GPT-4.1-nano para relevância setorial' },
  { icon: '📊', label: 'Análise de viabilidade', description: '4 fatores: modalidade, timeline, valor, geografia' },
];

const TESTIMONIAL_QUOTE = {
  text: 'O SmartLic nos ajudou a encontrar licitações que jamais encontraríamos manualmente. Em 3 meses, fechamos 2 contratos.',
  author: 'Empresa de Tecnologia',
  role: 'Setor de Informática',
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AutonomousLandingShell({
  entityType,
  entityName,
  entityDescription,
  children,
  ctaComponent,
  socialProof,
}: AutonomousLandingShellProps) {
  const config = ENTITY_CONFIG[entityType];
  const proof = socialProof ?? DEFAULT_SOCIAL_PROOF;

  return (
    <div className="min-h-screen flex flex-col bg-gray-50">
      <LandingNavbar />

      <main className="flex-1">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-10">
          {/* ── Hero / Title Section ── */}
          <section className="mb-8 sm:mb-12">
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-gray-900 mb-3 leading-tight">
              {entityName}
            </h1>
            {entityDescription && (
              <p className="text-sm sm:text-base text-gray-600 max-w-3xl leading-relaxed">
                {entityDescription}
              </p>
            )}
          </section>

          {/* ── CTA Area ── */}
          {ctaComponent && (
            <section className="mb-8 sm:mb-12">
              <div className="rounded-xl bg-blue-600 px-5 py-5 sm:px-6 sm:py-6 text-center sm:text-left sm:flex sm:items-center sm:justify-between sm:gap-4">
                <p className="text-sm sm:text-base text-blue-100 mb-4 sm:mb-0 sm:max-w-lg">
                  Monitore editais <span className="font-semibold text-white">{config.ctaSuffix}</span> e receba alertas automáticos em tempo real.
                </p>
                <div className="flex flex-col sm:flex-row gap-3 justify-center sm:justify-start">
                  {ctaComponent}
                  <Link
                    href="/observatorio"
                    className="inline-block whitespace-nowrap rounded-lg border border-white/30 px-5 py-2.5 text-sm font-medium text-white hover:bg-white/10 transition-colors text-center"
                  >
                    Só quero ver os dados
                  </Link>
                </div>
              </div>
            </section>
          )}

          {/* ── Social Proof Section ── */}
          {proof.length > 0 && (
            <section className="mb-8 sm:mb-12">
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
                {proof.map((item) => (
                  <div
                    key={item.label}
                    className="bg-white rounded-xl border border-gray-200 p-4 sm:p-5 text-center shadow-sm"
                  >
                    <p className="text-xl sm:text-2xl lg:text-3xl font-bold text-blue-700 mb-1">
                      {item.value}
                    </p>
                    <p className="text-xs sm:text-sm text-gray-500">{item.label}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* ── Main Content (children) ── */}
          <section className="mb-8 sm:mb-12">
            {children}
          </section>

          {/* ── What Is This Section ── */}
          <section className="mb-8 sm:mb-12">
            <div className="bg-white rounded-xl border border-gray-200 p-5 sm:p-7 shadow-sm">
              <h2 className="text-lg sm:text-xl font-semibold text-gray-900 mb-3">
                O que é o SmartLic?
              </h2>
              <p className="text-sm sm:text-base text-gray-600 leading-relaxed mb-4">
                {config.whatIsDescription}
              </p>
              <Link
                href="/sobre"
                className="inline-flex items-center text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
              >
                Saiba mais sobre a plataforma →
              </Link>
            </div>
          </section>

          {/* ── Trust Signals Section ── */}
          <section className="mb-8 sm:mb-12">
            <h2 className="text-lg sm:text-xl font-semibold text-gray-900 mb-4 text-center sm:text-left">
              Por que confiar no SmartLic?
            </h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              {TRUST_SIGNALS.map((signal) => (
                <div
                  key={signal.label}
                  className="bg-white rounded-xl border border-gray-200 p-4 sm:p-5 shadow-sm"
                >
                  <p className="text-2xl mb-2">{signal.icon}</p>
                  <p className="font-semibold text-gray-900 text-sm sm:text-base mb-1">
                    {signal.label}
                  </p>
                  <p className="text-xs sm:text-sm text-gray-500 leading-relaxed">
                    {signal.description}
                  </p>
                </div>
              ))}
            </div>

            {/* Testimonial */}
            <div className="mt-5 bg-blue-50 rounded-xl border border-blue-100 p-5 sm:p-6 shadow-sm">
              <blockquote className="text-sm sm:text-base text-gray-700 italic leading-relaxed mb-3">
                &ldquo;{TESTIMONIAL_QUOTE.text}&rdquo;
              </blockquote>
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-full bg-blue-200 flex items-center justify-center text-blue-700 font-bold text-sm">
                  {TESTIMONIAL_QUOTE.author.charAt(0)}
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-900">{TESTIMONIAL_QUOTE.author}</p>
                  <p className="text-xs text-gray-500">{TESTIMONIAL_QUOTE.role}</p>
                </div>
              </div>
            </div>
          </section>

          {/* ── Bottom CTA ── */}
          {ctaComponent && (
            <section className="mb-8">
              <div className="rounded-xl bg-gradient-to-r from-blue-600 to-blue-700 px-5 py-6 sm:px-8 sm:py-8 text-center shadow-lg">
                <h2 className="text-lg sm:text-xl font-bold text-white mb-2">
                  Não perca nenhuma licitação
                </h2>
                <p className="text-sm sm:text-base text-blue-100 mb-5 max-w-xl mx-auto">
                  Cadastre-se gratuitamente e receba alertas personalizados de editais compatíveis com seu negócio.
                </p>
                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <Link
                    href={`/signup?ref=autonomous-${entityType}&source=${encodeURIComponent(entityName)}`}
                    className="inline-block whitespace-nowrap rounded-lg bg-white px-6 py-3 text-sm font-semibold text-blue-700 hover:bg-blue-50 transition-colors shadow-sm"
                  >
                    Começar grátis →
                  </Link>
                  <Link
                    href="/planos"
                    className="inline-block whitespace-nowrap rounded-lg border border-white/30 px-6 py-3 text-sm font-medium text-white hover:bg-white/10 transition-colors"
                  >
                    Ver planos e preços
                  </Link>
                </div>
              </div>
            </section>
          )}
        </div>
      </main>

      <Footer />
    </div>
  );
}
