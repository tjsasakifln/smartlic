'use client';

import Link from 'next/link';

/**
 * API-SELF-005: Pricing cards para os 3 planos da API.
 * Segue padrão visual do PlanCard existente mas adaptado para API tiers.
 */

interface ApiTier {
  id: string;
  name: string;
  price: number;
  requests: string;
  features: string[];
  cta: string;
  highlighted: boolean;
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(price);
}

export function ApiPricingCards({ tiers }: { tiers: ApiTier[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-5xl mx-auto items-start">
      {tiers.map((tier) => (
        <div
          key={tier.id}
          className={`relative flex flex-col p-6 bg-surface-0 rounded-card border-2 transition-all duration-300 ${
            tier.highlighted
              ? 'border-brand-blue shadow-lg md:scale-105 md:-mt-2 md:-mb-2'
              : 'border-[var(--border)] hover:border-brand-blue/30 hover:shadow-md'
          }`}
          data-testid={`api-pricing-card-${tier.id}`}
        >
          {tier.highlighted && (
            <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-4 py-1 bg-brand-blue text-white text-xs font-bold rounded-full">
              Mais Popular
            </div>
          )}

          <div className="mb-6">
            <h3 className="text-lg font-bold text-ink font-display mb-1">
              {tier.name}
            </h3>
            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-bold text-ink">
                {formatPrice(tier.price)}
              </span>
              <span className="text-sm text-ink-muted">/mês</span>
            </div>
            <p className="text-xs text-ink-muted mt-1">
              {tier.requests} requisições/mês
            </p>
          </div>

          <ul className="space-y-2.5 mb-8 flex-1">
            {tier.features.map((feature) => (
              <li key={feature} className="flex items-start gap-2 text-sm text-ink-secondary">
                <svg
                  className="w-4 h-4 text-brand-blue flex-shrink-0 mt-0.5"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
                {feature}
              </li>
            ))}
          </ul>

          <Link
            href={tier.id === 'api_scale' ? '/contato' : `/checkout?plan=${tier.id}`}
            className={`block w-full py-2.5 rounded-button text-sm font-medium text-center transition-colors ${
              tier.highlighted
                ? 'bg-brand-navy text-white hover:bg-brand-blue'
                : 'bg-surface-1 text-ink border border-[var(--border)] hover:bg-surface-0 hover:border-brand-blue/50'
            }`}
          >
            {tier.cta}
          </Link>
        </div>
      ))}
    </div>
  );
}
