import { Metadata } from 'next';
import Link from 'next/link';
import LandingNavbar from '../components/landing/LandingNavbar';
import Footer from '../components/Footer';
import { ApiPricingCards } from './ApiPricingCards';

/**
 * API-SELF-005 (#1424): Landing page pública /api com documentação,
 * pricing cards dos 3 planos, e link para Swagger UI em /api/docs.
 */

export const metadata: Metadata = {
  title: 'SmartLic API — Integre Dados de Licitações Públicas',
  description:
    'Acesse dados estruturados de licitações públicas via API REST. Planos a partir de R$97/mês. Documentação interativa com Swagger UI.',
  alternates: {
    canonical: 'https://smartlic.tech/api',
  },
  openGraph: {
    title: 'SmartLic API — Dados de Licitações em Tempo Real',
    description:
      'API REST com dados de PNCP, PCP e ComprasGov. Autenticação por X-API-Key, rate limiting, e planos escaláveis.',
    type: 'website',
  },
};

function buildApiSchema() {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebAPI',
    name: 'SmartLic API',
    description:
      'API REST para consulta de licitações públicas com dados estruturados de PNCP, PCP v2 e ComprasGov.',
    url: 'https://smartlic.tech/api',
    documentation: 'https://smartlic.tech/api/docs',
    provider: {
      '@type': 'Organization',
      name: 'SmartLic',
      url: 'https://smartlic.tech',
    },
    offers: {
      '@type': 'Offer',
      price: '97.00',
      priceCurrency: 'BRL',
      description: 'Plano Starter — 1.000 requisições/mês',
    },
  };
}

const TIERS = [
  {
    id: 'api_starter',
    name: 'Starter',
    price: 97,
    requests: '1.000',
    features: [
      '1.000 requisições/mês',
      'Busca por palavra-chave e UF',
      'Filtro por modalidade',
      'Suporte por email (48h)',
      'Chave única',
    ],
    cta: 'Assinar Starter',
    highlighted: false,
  },
  {
    id: 'api_pro',
    name: 'Pro',
    price: 297,
    requests: '10.000',
    features: [
      '10.000 requisições/mês',
      'Todos os filtros (valor, data, modalidade)',
      'Dados históricos (até 400 dias)',
      'Suporte prioritário (24h)',
      'Até 3 chaves',
      'Webhooks de novos editais',
    ],
    cta: 'Assinar Pro',
    highlighted: true,
  },
  {
    id: 'api_scale',
    name: 'Scale',
    price: 970,
    requests: '100.000',
    features: [
      '100.000 requisições/mês',
      'Acesso a todos os endpoints',
      'Dados em tempo real',
      'Suporte dedicado (SLA 4h)',
      'Chaves ilimitadas',
      'IP whitelisting',
      'Contrato com SLA',
    ],
    cta: 'Falar com Vendas',
    highlighted: false,
  },
];

export default function ApiLandingPage() {
  const apiSchema = buildApiSchema();
  return (
    <div className="min-h-screen flex flex-col bg-canvas">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(apiSchema) }}
      />
      <LandingNavbar />

      <main className="flex-1">
        {/* Hero Section */}
        <section className="bg-surface-1 border-b border-[var(--border)]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 lg:py-20 text-center">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium bg-brand-blue/10 text-brand-blue mb-6">
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
              </svg>
              API REST
            </div>
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-ink tracking-tight mb-4 font-display">
              Dados de Licitações
              <br />
              <span className="text-brand-blue">via API</span>
            </h1>
            <p className="text-base sm:text-lg text-ink-secondary max-w-2xl mx-auto leading-relaxed">
              Integre dados estruturados de licitações públicas diretamente no seu
              sistema. Acesse PNCP, PCP v2 e ComprasGov com uma única API REST
              autenticada por chave.
            </p>

            <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/api/docs"
                className="px-6 py-3 rounded-button bg-brand-navy text-white font-medium hover:bg-brand-blue transition-colors"
              >
                Ver Documentação
              </Link>
              <Link
                href="/cadastro"
                className="px-6 py-3 rounded-button border-2 border-brand-blue text-brand-blue font-medium hover:bg-brand-blue hover:text-white transition-colors"
              >
                Criar Conta Gratuita
              </Link>
            </div>
          </div>
        </section>

        {/* Pricing Section */}
        <section className="py-16 sm:py-20 lg:py-24" id="precos">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h2 className="text-2xl sm:text-3xl font-bold text-ink font-display mb-4">
                Planos e Preços
              </h2>
              <p className="text-ink-secondary max-w-xl mx-auto">
                Escolha o plano ideal para o seu volume de consultas. Todos os
                planos incluem acesso à documentação interativa e suporte.
              </p>
            </div>

            <ApiPricingCards tiers={TIERS} />

            <p className="text-center text-xs text-ink-muted mt-8">
              Preços em reais (R$). Faturamento mensal via cartão de crédito ou PIX.
              Cancele a qualquer momento.
            </p>
          </div>
        </section>

        {/* Documentation Preview */}
        <section className="py-16 sm:py-20 bg-surface-1 border-y border-[var(--border)]" id="docs">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center mb-12">
              <h2 className="text-2xl sm:text-3xl font-bold text-ink font-display mb-4">
                Comece em minutos
              </h2>
              <p className="text-ink-secondary max-w-xl mx-auto">
                Autenticação simples por header, respostas em JSON, e documentação
                interativa com Swagger UI.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto">
              {/* Step 1 */}
              <div className="p-6 bg-surface-0 rounded-card border border-[var(--border)] text-center">
                <div className="w-10 h-10 rounded-full bg-brand-blue/10 text-brand-blue flex items-center justify-center mx-auto mb-4 font-bold text-sm">
                  1
                </div>
                <h3 className="font-semibold text-ink mb-2">Crie sua chave</h3>
                <p className="text-sm text-ink-secondary">
                  Cadastre-se e gere uma chave de API no painel da sua conta.
                  A chave tem o prefixo <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">sk_</code>.
                </p>
              </div>

              {/* Step 2 */}
              <div className="p-6 bg-surface-0 rounded-card border border-[var(--border)] text-center">
                <div className="w-10 h-10 rounded-full bg-brand-blue/10 text-brand-blue flex items-center justify-center mx-auto mb-4 font-bold text-sm">
                  2
                </div>
                <h3 className="font-semibold text-ink mb-2">Autentique</h3>
                <p className="text-sm text-ink-secondary">
                  Envie o header{' '}
                  <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">X-API-Key: sk_...</code>{' '}
                  em todas as requisições. Sem OAuth, sem JWT.
                </p>
              </div>

              {/* Step 3 */}
              <div className="p-6 bg-surface-0 rounded-card border border-[var(--border)] text-center">
                <div className="w-10 h-10 rounded-full bg-brand-blue/10 text-brand-blue flex items-center justify-center mx-auto mb-4 font-bold text-sm">
                  3
                </div>
                <h3 className="font-semibold text-ink mb-2">Faça a chamada</h3>
                <p className="text-sm text-ink-secondary">
                  GET <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">/v1/api/search?q=sua-consulta</code>.
                  Resposta em JSON com paginação e rate limiting.
                </p>
              </div>
            </div>

            {/* Code Sample */}
            <div className="mt-10 max-w-2xl mx-auto">
              <div className="bg-[var(--ink)] text-white rounded-card p-4 sm:p-6 overflow-x-auto">
                <p className="text-xs text-white/50 mb-3 font-mono"># Exemplo de requisição</p>
                <pre className="text-sm font-mono text-white/90 leading-relaxed">
                  <code>{`curl -X GET \\
  "https://api.smartlic.tech/v1/api/search?q=servi%C3%A7os+limpeza&uf=SP" \\
  -H "X-API-Key: sk_..." \\
  -H "Accept: application/json"`}</code>
                </pre>
              </div>
            </div>
          </div>
        </section>

        {/* Rate Limits & Auth */}
        <section className="py-16 sm:py-20">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="max-w-3xl mx-auto">
              <h2 className="text-2xl font-bold text-ink font-display mb-8 text-center">
                Autenticação e Rate Limits
              </h2>

              <div className="space-y-6">
                <div className="p-6 bg-surface-0 rounded-card border border-[var(--border)]">
                  <h3 className="font-semibold text-ink mb-2 flex items-center gap-2">
                    <svg className="w-5 h-5 text-brand-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
                    </svg>
                    Autenticação
                  </h3>
                  <p className="text-sm text-ink-secondary">
                    Header <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">X-API-Key: sk_...</code>.
                    Chaves são geradas no painel da conta e podem ser revogadas a qualquer momento.
                  </p>
                </div>

                <div className="p-6 bg-surface-0 rounded-card border border-[var(--border)]">
                  <h3 className="font-semibold text-ink mb-2 flex items-center gap-2">
                    <svg className="w-5 h-5 text-brand-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Rate Limiting
                  </h3>
                  <p className="text-sm text-ink-secondary mb-3">
                    Limites mensais por chave de API, reset no 1º dia do mês (00:00 BRT).
                    Headers <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">X-RateLimit-Limit</code> e{' '}
                    <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">X-RateLimit-Remaining</code> em
                    todas as respostas.
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {TIERS.map((tier) => (
                      <div key={tier.id} className="p-3 bg-surface-1 rounded-input text-center">
                        <p className="font-semibold text-ink text-sm">{tier.name}</p>
                        <p className="text-xs text-ink-muted">{tier.requests} req/mês</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="p-6 bg-surface-0 rounded-card border border-[var(--border)]">
                  <h3 className="font-semibold text-ink mb-2 flex items-center gap-2">
                    <svg className="w-5 h-5 text-brand-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    Formato de Resposta
                  </h3>
                  <p className="text-sm text-ink-secondary">
                    JSON com paginação: <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">pagina</code>,{' '}
                    <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">tamanho</code>,{' '}
                    <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">total</code>, e{' '}
                    <code className="px-1 py-0.5 bg-surface-1 rounded text-xs font-mono">resultados[]</code> com dados
                    estruturados de cada licitação.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* CTA Section */}
        <section className="py-16 sm:py-20 bg-brand-navy text-white">
          <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
            <h2 className="text-2xl sm:text-3xl font-bold font-display mb-4">
              Pronto para integrar?
            </h2>
            <p className="text-white/80 mb-8 max-w-xl mx-auto">
              Comece com o plano Starter e escale conforme sua necessidade.
              Documentação completa disponível no Swagger UI.
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/api/docs"
                className="px-6 py-3 rounded-button bg-white text-brand-navy font-medium hover:bg-white/90 transition-colors"
              >
                Explorar Swagger UI
              </Link>
              <Link
                href="/cadastro"
                className="px-6 py-3 rounded-button border-2 border-white/30 text-white font-medium hover:bg-white/10 transition-colors"
              >
                Criar Conta
              </Link>
            </div>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
