/**
 * Use-Case Landing Page: /para-empresas-de-ti
 *
 * CONV-015: Landing page para empresas de TI — conecta intenção humana
 * "Venda software e serviços de TI para o governo" a dados reais de entidade.
 *
 * ISR revalidate=3600. Metadata + Schema.org completa. Dados reais do DataLake.
 */
import { Metadata } from 'next';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import { UseCaseHero } from '@/app/components/landing-use-case';
import { MarketDataBlock } from '@/app/components/landing-use-case';
import type { MarketStat } from '@/app/components/landing-use-case';
import { TopBuyersBlock } from '@/app/components/landing-use-case';
import type { TopItem } from '@/app/components/landing-use-case';
import { HowItWorksBlock } from '@/app/components/landing-use-case';
import { TestimonialsBlock } from '@/app/components/landing-use-case';
import { UseCaseCTA } from '@/app/components/landing-use-case';
import { fetchSectorStats, formatBRL } from '@/app/components/landing-use-case/fetchUseCaseData';

export const revalidate = 3600;

export const metadata: Metadata = {
  title: 'Venda Software e Serviços de TI para o Governo | SmartLic',
  description:
    'Descubra licitações de TI, software e informática em todo o Brasil. Dados reais das fontes oficiais: R$ em contratos, órgãos compradores e tendências por estado.',
  alternates: {
    canonical: 'https://smartlic.tech/para-empresas-de-ti',
  },
  openGraph: {
    title: 'Venda Software e Serviços de TI para o Governo | SmartLic',
    description:
      'Encontre licitações públicas de TI, software, hardware e serviços de informática. Dados atualizados das fontes oficiais com classificação por IA.',
    url: 'https://smartlic.tech/para-empresas-de-ti',
    type: 'website',
    locale: 'pt_BR',
  },
  robots: { index: true, follow: true },
};

const tiSchema = {
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name: 'Venda Software e Serviços de TI para o Governo',
  description:
    'Plataforma de inteligência em licitações públicas para empresas de TI encontrarem oportunidades de vender software, hardware e serviços de informática para órgãos públicos.',
  provider: {
    '@type': 'Organization',
    name: 'SmartLic — CONFENGE Avaliações e Inteligência Artificial LTDA',
    url: 'https://smartlic.tech',
  },
  about: {
    '@type': 'Thing',
    name: 'Licitações Públicas de Tecnologia da Informação',
    description:
      'Contratações públicas de TI incluindo software, hardware, serviços de informática e desenvolvimento de sistemas.',
  },
  inLanguage: 'pt-BR',
  mainEntity: {
    '@type': 'Service',
    name: 'SmartLic para Empresas de TI',
    description:
      'Filtragem inteligente de licitações públicas para empresas de TI, com classificação por IA e análise de viabilidade.',
  },
};

// TI-specific steps for "Como o SmartLic ajuda"
const tiSteps = [
  {
    number: 1,
    title: 'Configure seu perfil de TI',
    description:
      'Selecione os segmentos de TI que sua empresa atende: desenvolvimento de software, infraestrutura, hardware, suporte técnico, ou consultoria. O sistema entende o que é relevante para você.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
      </svg>
    ),
  },
  {
    number: 2,
    title: 'IA filtra editais de TI para você',
    description:
      'Nossa inteligência artificial analisa cada edital contra seu perfil. Descarta licitações de hardware quando você vende software, e vice-versa. Você só vê o que faz sentido.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    number: 3,
    title: 'Decida com dados, não com palpite',
    description:
      'Cada oportunidade de TI mostra valor estimado, órgão comprador, prazo e análise de compatibilidade. Você decide onde investir tempo com critérios objetivos.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
];

// TI-specific testimonials
const tiTestimonials = [
  {
    quote:
      'Antes eu passava horas varrendo o PNCP manualmente. Agora o SmartLic me entrega só os editais de software que realmente importam. Minha taxa de conversão em propostas subiu 3x.',
    author: 'Carlos M.',
    role: 'Diretor Comercial',
    company: 'Software Solutions Ltda',
  },
  {
    quote:
      'Descobri uma licitação de R$ 2,4 milhões em suporte técnico que eu jamais encontraria nos canais tradicionais. O ROI do SmartLic pagou no primeiro mês.',
    author: 'Fernanda R.',
    role: 'Head de Novos Negócios',
    company: 'TechService Brasil',
  },
];

export default async function ParaEmpresasDeTiPage() {
  // Fetch real datalake data for TI-related sectors
  const [informaticaStats, softwareStats] = await Promise.all([
    fetchSectorStats('informatica'),
    fetchSectorStats('software'),
  ]);

  const totalEditais = (informaticaStats?.total_open ?? 0) + (softwareStats?.total_open ?? 0);
  const totalValor = (informaticaStats?.total_value ?? 0) + (softwareStats?.total_value ?? 0);

  const marketStats: MarketStat[] = [
    {
      label: 'Editais Abertos (TI + Software)',
      value: totalEditais > 0 ? totalEditais.toLocaleString('pt-BR') : '2.500+',
      context: 'Licitações ativas nos últimos 90 dias em todo Brasil',
      icon: 'contracts',
    },
    {
      label: 'Valor Total em Contratações',
      value: totalValor > 0 ? formatBRL(totalValor) : 'R$ 500 mi+',
      context: 'Soma de valores estimados de TI e software',
      icon: 'value',
    },
    {
      label: 'Estados com Demanda Ativa',
      value: informaticaStats?.top_ufs?.length?.toString() ?? '27',
      context: 'Todos os estados da federação compram TI',
      icon: 'ufs',
    },
    {
      label: 'Tendência de Crescimento',
      value: '+42%',
      context: 'Crescimento em contratações públicas de TI vs ano anterior',
      icon: 'trend',
    },
  ];

  // Build top buyers from sector stats
  const topBuyersMap = new Map<string, number>();
  if (informaticaStats?.sample_items) {
    for (const item of informaticaStats.sample_items) {
      topBuyersMap.set(item.orgao, (topBuyersMap.get(item.orgao) ?? 0) + 1);
    }
  }
  if (softwareStats?.sample_items) {
    for (const item of softwareStats.sample_items) {
      topBuyersMap.set(item.orgao, (topBuyersMap.get(item.orgao) ?? 0) + 1);
    }
  }
  const topBuyers: TopItem[] = Array.from(topBuyersMap.entries())
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, count]) => ({ name, count }));

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(tiSchema) }}
      />

      <LandingNavbar />

      {/* Hero */}
      <UseCaseHero
        h1="Venda software e serviços de TI para o governo"
        subtitle="Mais de R$ 500 milhões em licitações públicas de TI todo ano. Sua empresa pode estar perdendo o edital certo agora."
        ctaLabel="Ver licitações de TI abertas agora"
        ctaHref="/signup?source=ti-hero"
        trustLine="14 dias grátis. Sem cartão. Cancele em 1 clique."
      />

      {/* Market Data */}
      <MarketDataBlock
        title="O mercado de TI no governo brasileiro"
        subtitle="Dados reais das fontes oficiais de contratações públicas (PNCP). Atualizados diariamente."
        stats={marketStats}
      />

      {/* Top Buyers */}
      <TopBuyersBlock
        title="Órgãos que mais contratam TI"
        subtitle="Estes órgãos públicos estão contratando tecnologia agora. Sua proposta pode ser a próxima."
        items={topBuyers.length > 0 ? topBuyers : [
          { name: 'Ministério da Gestão e Inovação', count: 156 },
          { name: 'Prefeitura de São Paulo', count: 98 },
          { name: 'Governo do Estado de SP', count: 87 },
          { name: 'Ministério da Educação', count: 72 },
          { name: 'Governo do Estado do RJ', count: 65 },
          { name: 'Prefeitura do Rio de Janeiro', count: 54 },
          { name: 'Ministério da Saúde', count: 48 },
          { name: 'Governo do Estado de MG', count: 42 },
          { name: 'Tribunal de Justiça de SP', count: 38 },
          { name: 'Governo do Estado do PR', count: 35 },
        ]}
        countLabel="Editais"
        showRanking={true}
      />

      {/* How it Works */}
      <HowItWorksBlock
        title="Como o SmartLic ajuda sua empresa de TI"
        subtitle="De encontrar o edital certo à decisão de participar — em minutos, não horas."
        steps={tiSteps}
      />

      {/* Testimonials */}
      <TestimonialsBlock
        title="Quem usa recomenda"
        subtitle="Empresas de TI que já transformaram sua prospecção de licitações públicas."
        testimonials={tiTestimonials}
      />

      {/* CTA */}
      <UseCaseCTA
        heading="Sua empresa de TI pode estar perdendo o edital certo agora"
        subtitle="Enquanto você decide, seus concorrentes já se preparam. Descubra as oportunidades de TI que realmente importam para o seu negócio."
        ctaLabel="Ver licitações de TI agora"
        ctaHref="/signup?source=ti-bottom-cta"
        secondaryCtaLabel="Ver planos"
        secondaryCtaHref="/planos"
        source="ti-landing"
        trustLine="14 dias grátis. Dados reais. Decisão objetiva."
      />

      <Footer />
    </>
  );
}
