'use client';

import Link from 'next/link';
import type { ComponentProps } from 'react';
import { useAnalytics } from '../hooks/useAnalytics';

type LinkProps = ComponentProps<typeof Link>;

interface TrackingLinkProps extends Omit<LinkProps, 'onClick'> {
  /** Mixpanel event name to fire on click */
  eventName: string;
  /** Additional properties to include in the Mixpanel event */
  eventProps?: Record<string, unknown>;
  children: React.ReactNode;
  className?: string;
}

/**
 * TrackingLink — Client component wrapper around next/link that fires a
 * Mixpanel event on click.
 *
 * CONV-CTA-001: Used for programmatic SEO pages to track CTA interactions.
 *
 * @example
 * <TrackingLink
 *   href="/signup?utm_campaign=conv-cta-001"
 *   eventName="cta_clicked"
 *   eventProps={{ cta_name: 'contratos_orgao_hero', page_cnpj: cnpj }}
 *   className="..."
 * >
 *   Teste grátis por 14 dias
 * </TrackingLink>
 */
export function TrackingLink({
  href,
  eventName,
  eventProps,
  children,
  className,
  ...rest
}: TrackingLinkProps) {
  const { trackEvent } = useAnalytics();

  return (
    <Link
      href={href}
      className={className}
      onClick={() => trackEvent(eventName, eventProps)}
      {...rest}
    >
      {children}
    </Link>
  );
}

export default TrackingLink;
