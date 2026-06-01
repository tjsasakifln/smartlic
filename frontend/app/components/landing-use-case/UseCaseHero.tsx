/**
 * UseCaseHero — Hero section for use-case landing pages
 *
 * RSC with H1 focused on economic consequence, subtitle, and contextual CTA.
 * Used by /para-empresas-de-ti, /para-construtoras, /para-quem-quer-subcontratar.
 */
import Link from 'next/link';

interface UseCaseHeroProps {
  h1: string;
  subtitle: string;
  ctaLabel: string;
  ctaHref: string;
  trustLine?: string;
}

export default function UseCaseHero({
  h1,
  subtitle,
  ctaLabel,
  ctaHref,
  trustLine,
}: UseCaseHeroProps) {
  return (
    <section className="bg-gradient-to-br from-brand-blue to-brand-blue/80 text-white py-20 sm:py-28">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl">
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold mb-6 leading-tight">
            {h1}
          </h1>
          <p className="text-xl sm:text-2xl text-white/90 mb-8 leading-relaxed">
            {subtitle}
          </p>
          <Link
            href={ctaHref}
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
          </Link>
          {trustLine && (
            <p className="mt-4 text-sm text-white/70">{trustLine}</p>
          )}
        </div>
      </div>
    </section>
  );
}
