'use client';

/**
 * UseCaseCTA — Final CTA block with Mixpanel tracking for use-case landing pages
 *
 * Client component because it uses trackCTAClick for analytics.
 * Renders a contextual CTA with gradient background.
 */
import { trackCTAClick } from '@/lib/analytics-events';

interface UseCaseCTAProps {
  heading: string;
  subtitle: string;
  ctaLabel: string;
  ctaHref: string;
  source: string;
  secondaryCtaLabel?: string;
  secondaryCtaHref?: string;
  trustLine?: string;
}

export default function UseCaseCTA({
  heading,
  subtitle,
  ctaLabel,
  ctaHref,
  source,
  secondaryCtaLabel,
  secondaryCtaHref,
  trustLine,
}: UseCaseCTAProps) {
  const handlePrimaryClick = () => {
    trackCTAClick({
      label: `${source}-primary`,
      source,
      destination: ctaHref,
      cta_type: 'self-service',
    });
  };

  const handleSecondaryClick = () => {
    if (secondaryCtaHref) {
      trackCTAClick({
        label: `${source}-secondary`,
        source,
        destination: secondaryCtaHref,
        cta_type: 'self-service',
      });
    }
  };

  return (
    <section className="py-20 bg-gradient-to-br from-brand-blue to-brand-blue/80 text-white">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
        <h2 className="text-3xl sm:text-4xl font-bold mb-6">
          {heading}
        </h2>
        <p className="text-xl text-white/90 mb-8 max-w-2xl mx-auto">
          {subtitle}
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <a
            href={ctaHref}
            onClick={handlePrimaryClick}
            className="inline-flex items-center gap-2 bg-white text-brand-blue px-8 py-4 rounded-lg font-semibold hover:bg-white/90 transition-colors focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand-blue text-lg"
          >
            <span>{ctaLabel}</span>
            <svg
              role="img"
              aria-label="Seta para direita"
              className="w-5 h-5"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 7l5 5m0 0l-5 5m5-5H6"
              />
            </svg>
          </a>

          {secondaryCtaLabel && secondaryCtaHref && (
            <a
              href={secondaryCtaHref}
              onClick={handleSecondaryClick}
              className="inline-flex items-center border border-white/40 text-white hover:bg-white/10 font-semibold px-8 py-4 rounded-lg transition-colors text-center text-base focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-white/50"
            >
              {secondaryCtaLabel}
            </a>
          )}
        </div>

        {trustLine && (
          <p className="mt-4 text-sm text-white/70">{trustLine}</p>
        )}
      </div>
    </section>
  );
}
