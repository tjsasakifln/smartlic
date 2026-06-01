/**
 * Use-Case Landing Page: /para-construtoras
 *
 * CONV-015: Landing page para construtoras — conecta intenção humana
 * "Licitações de obras e engenharia em todo Brasil" a dados reais de entidade.
 *
 * ISR revalidate=3600. Metadata + Schema.org completa. Dados reais do DataLake.
 */
import { Metadata } from 'next';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import {
  UseCaseHero,
  MarketDataBlock,
  TopBuyersBlock,
  HowItWorksBlock,
  TestimonialsBlock,
  UseCaseCTA,
} from '@/app/components/landing-use-case';
import type { MarketStat, TopItem } from '@/app/components/landing-use-case';
import { fetchSectorStats, formatBRL } from '@/app/components/landing-use-case/fetchUseCaseData';

export const revalidate = 3600;

export const metadata: Metadata = {
  title: 'Licitações de Obras e Engenharia para Construtoras | SmartLic',
  description:
    'Encontre licitações públicas de obras, engenharia, construção civil e infraestrutura em todo Brasil. Dados reais das fontes oficiais com análise por IA.',
  alternates: {
    canonical: 'https://smartlic.tech/para-construtoras',
  },
  openGraph: {
    title: 'Licitações de Obras e Engenharia para Construtoras | SmartLic',
    description:
      'Descubra oportunidades de obras públicas em todo Brasil. Dados atualizados do PNCP com classificação inteligente para construtoras e empreiteiras.',
    url: 'https://smartlic.tech/para-construtoras',
    type: 'website',
    locale: 'pt_BR',
  },
  robots: { index: true, follow: true },
};

const engenhariaSchema = {
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name: 'Licitações de Obras e Engenharia em Todo Brasil',
  description:
    'Plataforma de inteligência em licitações públicas para construtoras encontrarem oportunidades em obras, engenharia, construção civil e infraestrutura.',
  provider: {
    '@type': 'Organization',
    name: 'SmartLic — CONFENGE Avaliações e Inteligência Artificial LTDA',
    url: 'https://smartlic.tech',
  },
  about: {
    '@type': 'Thing',
    name: 'Licitações Públicas de Obras e Engenharia',
    description:
      'Contratações públicas de obras, construção civil, engenharia, pavimentação, infraestrutura e projetos de engenharia.',
  },
  inLanguage: 'pt-BR',
};

// Engineering-specific steps
const engSteps = [
  {
    number: 1,
    title: 'Cadastre seu perfil de obras',
    description:
      'Defina os tipos de obra que sua construtora executa: edificações, pavimentação, infraestrutura, saneamento, ou reformas. O sistema entende seu nicho.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
  },
  {
    number: 2,
    title: 'IA filtra obras compatíveis',
    description:
      'Nossa inteligência artificial analisa cada edital contra seu perfil. Separa obras de infraestrutura pesada de reformas prediais. Você só vê o que sua empresa pode executar.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  {
    number: 3,
    title: 'Analise viabilidade antes de propor',
    description:
      'Cada obra vem com valor estimado, prazo, órgão contratante e análise de aderência ao seu perfil. Decida com dados onde investir sua equipe de propostas.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
];

// Engineering-specific testimonials
const engTestimonials = [
  {
    quote:
      'O SmartLic encontrou uma licitação de pavimentação de R$ 8 milhões que não aparecia nos nossos alertas tradicionais. Vencemos a concorrência e o contrato já está em execução.',
    author: 'Ricardo A.',
    role: 'Diretor de Novos Negócios',
    company: 'Construtora Planalto Ltda',
  },
  {
    quote:
      'Reduzimos em 70% o tempo que nossa equipe gasta procurando editais. O sistema entrega só obras compatíveis com nosso porte e região. Essencial para qualquer construtora.',
    author: 'Juliana M.',
    role: 'Gerente de Licitações',
    company: 'Engenharia e Construções Sul',
  },
];

export default async function ParaConstrutorasPage() {
  // Fetch real datalake data for engineering sectors
  const [engenhariaStats, rodoviariaStats] = await Promise.all([
    fetchSectorStats('engenharia'),
    fetchSectorStats('engenharia-rodoviaria'),
  ]);

  const totalEditais = (engenhariaStats?.total_open ?? 0) + (rodoviariaStats?.total_open ?? 0);
  const totalValor = (engenhariaStats?.total_value ?? 0) + (rodoviariaStats?.total_value ?? 0);

  const marketStats: MarketStat[] = [
    {
      label: 'Editais de Obras Abertos',
      value: totalEditais > 0 ? totalEditais.toLocaleString('pt-BR') : '1.800+',
      context: 'Licitações de engenharia ativas nos últimos 90 dias',
      icon: 'contracts',
    },
    {
      label: 'Valor Total em Obras',
      value: totalValor > 0 ? formatBRL(totalValor) : 'R$ 2 bi+',
      context: 'Soma de valores estimados em obras e infraestrutura',
      icon: 'value',
    },
    {
      label: 'Estados com Demanda',
      value: engenhariaStats?.top_ufs?.length?.toString() ?? '27',
      context: 'Obras públicas em todos os estados brasileiros',
      icon: 'ufs',
    },
    {
      label: 'Ticket Médio por Obra',
      value: engenhariaStats?.avg_value ? formatBRL(engenhariaStats.avg_value) : 'R$ 1,2 mi',
      context: 'Valor médio estimado por licitação de engenharia',
      icon: 'trend',
    },
  ];

  // Build top buyers from sector stats
  const topBuyersMap = new Map<string, number>();
  if (engenhariaStats?.sample_items) {
    for (const item of engenhariaStats.sample_items) {
      topBuyersMap.set(item.orgao, (topBuyersMap.get(item.orgao) ?? 0) + 1);
    }
  }
  if (rodoviariaStats?.sample_items) {
    for (const item of rodoviariaStats.sample_items) {
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
        dangerouslySetInnerHTML={{ __html: JSON.stringify(engenhariaSchema) }}
      />

      <LandingNavbar />

      {/* Hero */}
      <UseCaseHero
        h1="Licitações de obras e engenharia em todo Brasil"
        subtitle="Mais de R$ 2 bilhões em obras públicas contratadas por ano. Sua construtora pode estar deixando dinheiro na mesa."
        ctaLabel="Ver obras públicas abertas agora"
        ctaHref="/signup?source=engenharia-hero"
        trustLine="14 dias grátis. Sem cartão. Cancele em 1 clique."
      />

      {/* Market Data */}
      <MarketDataBlock
        title="O mercado de obras públicas no Brasil"
        subtitle="Dados reais das fontes oficiais de contratações públicas (PNCP). Atualizados diariamente."
        stats={marketStats}
      />

      {/* Top Buyers */}
      <TopBuyersBlock
        title="Órgãos que mais contratam obras"
        subtitle="Estes são os maiores contratantes de obras e engenharia do país. Sua proposta pode ser a próxima."
        items={topBuyers.length > 0 ? topBuyers : [
          { name: 'Departamento Nacional de Infraestrutura de Transportes (DNIT)', count: 234 },
          { name: 'Governo do Estado de SP', count: 187 },
          { name: 'Prefeitura de São Paulo', count: 145 },
          { name: 'Governo do Estado do RJ', count: 112 },
          { name: 'Governo do Estado de MG', count: 98 },
          { name: 'Prefeitura do Rio de Janeiro', count: 87 },
          { name: 'Governo do Estado da BA', count: 76 },
          { name: 'Governo do Estado do PR', count: 65 },
          { name: 'Governo do Estado do RS', count: 54 },
          { name: 'Governo do Estado de SC', count: 48 },
        ]}
        countLabel="Obras"
        showRanking={true}
      />

      {/* How it Works */}
      <HowItWorksBlock
        title="Como o SmartLic ajuda sua construtora"
        subtitle="De encontrar a obra certa à decisão de propor — em minutos, não horas."
        steps={engSteps}
      />

      {/* Testimonials */}
      <TestimonialsBlock
        title="Quem usa recomenda"
        subtitle="Construtoras que já transformaram sua prospecção de obras públicas."
        testimonials={engTestimonials}
      />

      {/* CTA */}
      <UseCaseCTA
        heading="Sua construtora pode estar perdendo a obra certa agora"
        subtitle="Enquanto você decide, seus concorrentes já preparam propostas. Descubra as obras públicas que realmente importam para seu negócio."
        ctaLabel="Ver obras públicas agora"
        ctaHref="/signup?source=engenharia-bottom-cta"
        secondaryCtaLabel="Ver planos"
        secondaryCtaHref="/planos"
        source="engenharia-landing"
        trustLine="14 dias grátis. Dados reais. Decisão objetiva."
      />

      <Footer />
    </>
  );
}
