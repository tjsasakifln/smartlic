'use client';

import Link from 'next/link';
import { useState, useCallback } from 'react';
import type { CtaConfig } from '@/lib/cta-intent';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type CtaVariant = 'inline' | 'hero';

export interface CtaIntentProps {
  /** The full CTA configuration from getCtaByIntent() or custom config. */
  config: CtaConfig;
  /** Visual variant. inline = compact mid-page, hero = full-width end-of-page. */
  variant: CtaVariant;
  /** Optional extra CSS classes for the wrapper. */
  className?: string;
}

// ---------------------------------------------------------------------------
// Style helpers
// ---------------------------------------------------------------------------

const VARIANT_STYLES: Record<CtaVariant, {
  outer: string;
  headline: string;
  subtext: string;
  button: string;
  secondary: string;
  socialProof: string;
  microfiltroChip: string;
  microfiltroChipActive: string;
}> = {
  inline: {
    outer:
      'not-prose my-8 sm:my-10 bg-brand-blue-subtle/50 rounded-lg p-4 sm:p-5 '
      + 'border border-brand-blue/15',
    headline: 'text-base sm:text-lg font-bold text-ink',
    subtext: 'text-sm sm:text-base text-ink-secondary',
    button:
      'inline-block bg-brand-navy hover:bg-brand-blue-hover text-white font-semibold '
      + 'px-4 py-2 rounded-button text-sm transition-all hover:scale-[1.02] active:scale-[0.98] '
      + 'whitespace-nowrap',
    secondary: 'text-sm text-brand-blue hover:text-brand-blue-hover font-medium transition-colors',
    socialProof: 'text-xs text-ink-muted mt-2',
    microfiltroChip:
      'px-3 py-1.5 text-sm rounded-full border border-[var(--border)] '
      + 'text-ink-secondary hover:bg-surface-1 hover:text-ink transition-colors cursor-pointer',
    microfiltroChipActive:
      'bg-brand-navy text-white border-brand-navy',
  },
  hero: {
    outer:
      'not-prose mt-12 mb-8 bg-gradient-to-br from-brand-navy to-brand-blue '
      + 'rounded-xl p-6 sm:p-8 text-white text-center',
    headline: 'text-xl sm:text-2xl font-bold mb-3',
    subtext: 'text-white/80 mb-6 max-w-xl mx-auto text-sm sm:text-base',
    button:
      'inline-block bg-white text-brand-navy font-semibold px-6 py-3 rounded-button '
      + 'transition-all hover:scale-[1.02] active:scale-[0.98]',
    secondary: 'text-sm text-white/70 hover:text-white font-medium transition-colors',
    socialProof: 'text-xs text-white/60 mt-3',
    microfiltroChip:
      'px-3 py-1.5 text-sm rounded-full border border-white/30 '
      + 'text-white/80 hover:bg-white/10 hover:text-white transition-colors cursor-pointer',
    microfiltroChipActive:
      'bg-white text-brand-navy border-white',
  },
};

// ---------------------------------------------------------------------------
// Microfiltro sub-component
// ---------------------------------------------------------------------------

interface MicrofiltroProps {
  config: NonNullable<CtaConfig['microfiltro']>;
  styles: ReturnType<typeof getVariantStyles>;
}

function Microfiltro({ config, styles }: MicrofiltroProps) {
  const [active, setActive] = useState<string>(config.options[0]?.value ?? 'todos');

  const handleSelect = useCallback((value: string) => {
    setActive(value);
  }, []);

  return (
    <div className="flex flex-wrap items-center gap-2 mb-4" role="group" aria-label={config.label}>
      <span className="text-xs font-medium text-ink-muted mr-1">{config.label}:</span>
      {config.options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => handleSelect(opt.value)}
          className={`${styles.microfiltroChip} ${active === opt.value ? styles.microfiltroChipActive : ''}`}
          aria-pressed={active === opt.value}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

/**
 * Reusable CTA component driven by CtaConfig from the intent-based system.
 *
 * Two variants:
 * - `inline` (compact, for mid-page insertion)
 * - `hero` (prominent full-width, for end-of-page)
 *
 * Renders headline, subtext, primary button, optional secondary action,
 * optional microfiltro (pre-segmentation), and optional social proof.
 *
 * @example
 *   const cta = getCtaByIntent('setorial-com-editais', { setor: 'TI', count: 42, slug: 'ti' });
 *   <CtaIntent config={cta} variant="inline" />
 */
export function CtaIntent({ config, variant, className = '' }: CtaIntentProps) {
  const styles = VARIANT_STYLES[variant];
  const isMonitoring = config.monitoringCta;

  return (
    <section
      className={`${styles.outer} ${className}`}
      role="complementary"
      aria-label={isMonitoring ? 'Monitoramento de oportunidades' : 'Chamada para acao'}
      data-page-type={config.pageType}
      data-campaign={config.campaign}
    >
      {/* Microfiltro (pre-segmentation) — shown only in inline variant */}
      {config.microfiltro && variant === 'inline' && (
        <Microfiltro config={config.microfiltro} styles={styles} />
      )}

      <div className={variant === 'inline' ? 'flex flex-col sm:flex-row items-center gap-3 sm:gap-4' : ''}>
        {/* Text content */}
        <div className={variant === 'inline' ? 'flex-1 text-center sm:text-left' : ''}>
          <h2 className={styles.headline}>{config.headline}</h2>
          <p className={styles.subtext}>{config.subtext}</p>
        </div>

        {/* Actions */}
        <div className={`flex flex-col items-center gap-2 ${variant === 'inline' ? 'flex-shrink-0' : ''}`}>
          {/* Primary button */}
          <Link
            href={config.buttonLink}
            className={styles.button}
            aria-label={config.buttonText}
          >
            {config.buttonText}
          </Link>

          {/* Secondary action (lighter weight) */}
          {config.secondaryText && config.secondaryLink && (
            <Link
              href={config.secondaryLink}
              className={styles.secondary}
              aria-label={config.secondaryText}
            >
              {config.secondaryText}
            </Link>
          )}
        </div>
      </div>

      {/* Social proof */}
      {config.socialProof && (
        <p className={styles.socialProof} aria-label={config.socialProof}>
          {config.socialProof}
        </p>
      )}
    </section>
  );
}

// ---------------------------------------------------------------------------
// Type export helper (used by parent components to derive styles)
// ---------------------------------------------------------------------------

function getVariantStyles(variant: CtaVariant) {
  return VARIANT_STYLES[variant];
}
