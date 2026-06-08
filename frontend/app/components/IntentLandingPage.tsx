'use client';

import Link from 'next/link';
import { useMemo } from 'react';
import type { IntentCluster } from '@/app/components/conversion/IntentRouter';

export interface Step {
  title: string;
  description: string;
}

export interface CtaAction {
  text: string;
  href: string;
}

export interface IntentLandingPageProps {
  /** Intent cluster used for tracking and visual theming */
  cluster: IntentCluster;
  /** Hero headline (h1) */
  headline: string;
  /** Hero subtitle */
  subtitle: string;
  /** 3 how-it-works steps */
  steps: Step[];
  /** Social proof / credibility text */
  socialProofText: string;
  /** Primary CTA button config */
  ctaPrimary: CtaAction;
  /** Secondary CTA link config */
  ctaSecondary: CtaAction;
  /** Page title for JSON-LD structured data */
  pageTitle: string;
  /** Page description for JSON-LD structured data */
  pageDescription: string;
}

/**
 * Reusable landing page component for intent-based conversion pages.
 *
 * Renders a hero, how-it-works steps, social proof, and dual-CTAs.
 * Includes JSON-LD structured data for SEO.
 * Matches the SmartLic design language (blue/green, rounded corners, shadows).
 */
export default function IntentLandingPage({
  cluster,
  headline,
  subtitle,
  steps,
  socialProofText,
  ctaPrimary,
  ctaSecondary,
  pageTitle,
  pageDescription,
}: IntentLandingPageProps) {
  const schema = useMemo(
    () => ({
      '@context': 'https://schema.org',
      '@type': 'WebPage',
      name: pageTitle,
      description: pageDescription,
      provider: {
        '@type': 'Organization',
        name: 'SmartLic',
        url: 'https://smartlic.tech',
      },
      inLanguage: 'pt-BR',
    }),
    [pageTitle, pageDescription],
  );

  return (
    <>
      {/* JSON-LD structured data for SEO */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(schema) }}
      />

      <main>
        {/* ── Hero Section ────────────────────────────────────────────── */}
        <section
          aria-label="Hero"
          className="relative bg-gradient-to-br from-brand-navy to-brand-blue text-white py-20 px-4"
        >
          <div className="max-w-4xl mx-auto text-center">
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold leading-tight mb-6">
              {headline}
            </h1>
            <p className="text-lg sm:text-xl text-white/80 max-w-2xl mx-auto mb-8">
              {subtitle}
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <Link
                href={ctaPrimary.href}
                className="inline-block bg-green-600 hover:bg-green-700 text-white font-semibold px-8 py-4 rounded-xl transition-all hover:scale-[1.02] active:scale-[0.98] shadow-lg focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-white/50 focus-visible:ring-offset-2 focus-visible:ring-offset-brand-navy w-full sm:w-auto text-center"
              >
                {ctaPrimary.text}
              </Link>
              <Link
                href={ctaSecondary.href}
                className="inline-block text-white/80 hover:text-white font-medium px-6 py-4 underline underline-offset-2 transition-colors focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-white/50 focus-visible:ring-offset-2 focus-visible:ring-offset-brand-navy rounded"
              >
                {ctaSecondary.text}
              </Link>
            </div>
          </div>
        </section>

        {/* ── How It Works Section ────────────────────────────────────── */}
        <section aria-label="Como funciona" className="py-16 px-4 bg-canvas">
          <div className="max-w-4xl mx-auto">
            <h2 className="text-2xl sm:text-3xl font-bold text-center text-ink mb-12">
              Como funciona
            </h2>
            <div className="grid sm:grid-cols-3 gap-8">
              {steps.map((step, index) => (
                <article key={index} className="text-center">
                  <div
                    className="w-12 h-12 bg-brand-blue/10 rounded-full flex items-center justify-center mx-auto mb-4"
                    aria-hidden="true"
                  >
                    <span className="text-brand-blue font-bold text-lg">
                      {index + 1}
                    </span>
                  </div>
                  <h3 className="font-bold text-lg text-ink mb-2">
                    {step.title}
                  </h3>
                  <p className="text-ink-secondary text-sm leading-relaxed">
                    {step.description}
                  </p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ── Social Proof Section ────────────────────────────────────── */}
        <section aria-label="Credibilidade" className="py-16 px-4 bg-surface-1 border-y border-[var(--border)]">
          <div className="max-w-3xl mx-auto text-center">
            <div className="bg-canvas rounded-2xl p-8 shadow-sm border border-[var(--border)]">
              <p className="text-lg text-ink-secondary leading-relaxed">
                {socialProofText}
              </p>
            </div>
          </div>
        </section>

        {/* ── Final CTA Section ────────────────────────────────────────── */}
        <section aria-label="Chamada para acao" className="py-20 px-4 bg-canvas">
          <div className="max-w-3xl mx-auto text-center">
            <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
              <Link
                href={ctaPrimary.href}
                className="inline-block bg-green-600 hover:bg-green-700 text-white font-bold px-10 py-4 rounded-xl text-lg transition-all hover:scale-[1.02] active:scale-[0.98] shadow-lg focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 w-full sm:w-auto text-center"
              >
                {ctaPrimary.text}
              </Link>
              <Link
                href={ctaSecondary.href}
                className="inline-block text-brand-blue hover:text-brand-blue-hover font-medium px-6 py-4 underline underline-offset-2 transition-colors focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 rounded"
              >
                {ctaSecondary.text}
              </Link>
            </div>
          </div>
        </section>
      </main>
    </>
  );
}
