import type { Metadata } from 'next';

/**
 * API-SELF-005: Layout compartilhado para /api e /api/docs.
 * Fornece metadados base que podem ser sobrescritos por cada página.
 */

export const metadata: Metadata = {
  title: {
    default: 'SmartLic API — Integre Dados de Licitações Públicas',
    template: '%s — SmartLic API',
  },
  description:
    'Acesse dados estruturados de licitações públicas via API REST. Planos a partir de R$97/mês. Documentação interativa com Swagger UI.',
  alternates: {
    canonical: 'https://smartlic.tech/api',
  },
  openGraph: {
    siteName: 'SmartLic',
    title: 'SmartLic API — Dados de Licitações em Tempo Real',
    description:
      'API REST com dados de PNCP, PCP e ComprasGov. Autenticação por X-API-Key, rate limiting, e planos escaláveis.',
    type: 'website',
    url: 'https://smartlic.tech/api',
  },
};

export default function ApiLayout({ children }: { children: React.ReactNode }) {
  return <>{children}</>;
}
