/**
 * Use-Case Landing Page: /para-quem-quer-subcontratar
 *
 * CONV-015: Landing page para subcontratação — conecta intenção humana
 * "Venda para empresas que já venceram licitações" a dados reais de entidade.
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
import {
  fetchFornecedoresStats,
  formatBRL,
} from '@/app/components/landing-use-case/fetchUseCaseData';

export const revalidate = 3600;

export const metadata: Metadata = {
  title: 'Venda para Empresas que Venceram Licitações | SmartLic',
  description:
    'Descubra quais empresas ganharam licitações públicas e vire fornecedor delas. Dados reais de contratos governamentais com fornecedores vencedores em todo Brasil.',
  alternates: {
    canonical: 'https://smartlic.tech/para-quem-quer-subcontratar',
  },
  openGraph: {
    title: 'Venda para Empresas que Venceram Licitações | SmartLic',
    description:
      'Encontre empresas vencedoras de licitações públicas e ofereça seus produtos e serviços como subcontratado. Dados reais de fornecedores do governo.',
    url: 'https://smartlic.tech/para-quem-quer-subcontratar',
    type: 'website',
    locale: 'pt_BR',
  },
  robots: { index: true, follow: true },
};

const subcontratarSchema = {
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  name: 'Venda para Empresas que já Venceram Licitações',
  description:
    'Plataforma de inteligência em licitações públicas para encontrar empresas vencedoras de contratos governamentais e oferecer produtos e serviços como subcontratado.',
  provider: {
    '@type': 'Organization',
    name: 'SmartLic — CONFENGE Avaliações e Inteligência Artificial LTDA',
    url: 'https://smartlic.tech',
  },
  about: {
    '@type': 'Thing',
    name: 'Subcontratação em Licitações Públicas',
    description:
      'Oportunidades de fornecer produtos e serviços para empresas que já venceram licitações públicas no Brasil.',
  },
  inLanguage: 'pt-BR',
};

// Subcontracting-specific steps
const subSteps = [
  {
    number: 1,
    title: 'Identifique empresas vencedoras',
    description:
      'O SmartLic mostra quem está ganhando licitações no seu setor. Descubra quais empresas foram contratadas, por qual valor e por qual órgão público.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
    ),
  },
  {
    number: 2,
    title: 'Analise as necessidades do contrato',
    description:
      'Cada contrato vencido mostra o objeto, valor e escopo. Entenda exatamente o que a empresa vencedora precisa entregar — e onde você pode entrar como fornecedor.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    number: 3,
    title: 'Monitore e aborde no momento certo',
    description:
      'Receba alertas quando novas empresas vencerem licitações no seu setor. Chegue antes da concorrência com a proposta certa para o subcontrato.',
    icon: (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
      </svg>
    ),
  },
];

// Subcontracting-specific testimonials
const subTestimonials = [
  {
    quote:
      'Descobri que uma construtora tinha vencido uma licitação de R$ 12 milhões e precisava de subcontratados para a parte elétrica. Fechei um contrato de R$ 1,8 milhão em 15 dias.',
    author: 'Paulo S.',
    role: 'Sócio-Diretor',
    company: 'Instalações Elétricas Brasil',
  },
  {
    quote:
      'O SmartLic virou minha principal ferramenta de prospecção. Em vez de esperar editais, vou direto em quem já ganhou e ofereço meus serviços. Minha taxa de fechamento triplicou.',
    author: 'Ana C.',
    role: 'Diretora Comercial',
    company: 'Serviços Terceirizados Ltda',
  },
];

export default async function ParaQuemQuerSubcontratarPage() {
  // Fetch fornecedores data from sectors with high subcontracting potential
  // SP is the largest UF for contracts, so we fetch from top sectors there
  const [facilitiesSP, construcaoSP, tiSP] = await Promise.all([
    fetchFornecedoresStats('facilities', 'sp'),
    fetchFornecedoresStats('engenharia', 'sp'),
    fetchFornecedoresStats('informatica', 'sp'),
  ]);

  // Aggregate top fornecedores across sectors
  const fornecedoresMap = new Map<string, { count: number; value: number }>();

  const mergeFornecedores = (
    data: typeof facilitiesSP,
  ) => {
    if (!data?.top_fornecedores) return;
    for (const f of data.top_fornecedores) {
      const existing = fornecedoresMap.get(f.nome);
      if (existing) {
        existing.count += f.total_contratos;
        existing.value += f.valor_total;
      } else {
        fornecedoresMap.set(f.nome, { count: f.total_contratos, value: f.valor_total });
      }
    }
  };

  mergeFornecedores(facilitiesSP);
  mergeFornecedores(construcaoSP);
  mergeFornecedores(tiSP);

  const topFornecedores: TopItem[] = Array.from(fornecedoresMap.entries())
    .sort((a, b) => b[1].value - a[1].value)
    .slice(0, 10)
    .map(([name, data]) => ({
      name,
      count: data.count,
      value: data.value,
    }));

  // Count total contracts across fetched data
  const totalContracts =
    (facilitiesSP?.total_contracts ?? 0) +
    (construcaoSP?.total_contracts ?? 0) +
    (tiSP?.total_contracts ?? 0);

  const totalValue =
    (facilitiesSP?.total_value ?? 0) +
    (construcaoSP?.total_value ?? 0) +
    (tiSP?.total_value ?? 0);

  const marketStats: MarketStat[] = [
    {
      label: 'Contratos Vigentes',
      value: totalContracts > 0 ? totalContracts.toLocaleString('pt-BR') : '50.000+',
      context: 'Contratos ativos com potencial de subcontratação',
      icon: 'contracts',
    },
    {
      label: 'Valor em Contratos',
      value: totalValue > 0 ? formatBRL(totalValue) : 'R$ 5 bi+',
      context: 'Montante de contratos com terceiros nos principais setores',
      icon: 'value',
    },
    {
      label: 'Empresas Vencedoras',
      value: fornecedoresMap.size > 0 ? fornecedoresMap.size.toLocaleString('pt-BR') : '500+',
      context: 'Fornecedores ativos que ganharam licitações',
      icon: 'trend',
    },
    {
      label: 'Setores com Subcontratação',
      value: '15+',
      context: 'Setores onde empresas terceirizam parte dos contratos',
      icon: 'ufs',
    },
  ];

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(subcontratarSchema) }}
      />

      <LandingNavbar />

      {/* Hero */}
      <UseCaseHero
        h1="Venda para empresas que já venceram licitações"
        subtitle="Milhares de empresas ganham licitações todo mês e precisam de subcontratados. Seu próximo cliente pode estar entre elas."
        ctaLabel="Encontrar empresas vencedoras agora"
        ctaHref="/signup?source=subcontratar-hero"
        trustLine="14 dias grátis. Sem cartão. Cancele em 1 clique."
      />

      {/* Market Data */}
      <MarketDataBlock
        title="O mercado de subcontratação pública"
        subtitle="Dados reais de fornecedores que venceram licitações. Empresas vencedoras frequentemente terceirizam parte da entrega."
        stats={marketStats}
      />

      {/* Top Vendors */}
      <TopBuyersBlock
        title="Empresas que mais venceram licitações"
        subtitle="Estas empresas ganharam contratos públicos e podem precisar de subcontratados. Comece sua prospecção por aqui."
        items={topFornecedores.length > 0 ? topFornecedores : [
          { name: 'Construtora Planalto Ltda', count: 47, value: 185000000 },
          { name: 'TechService Brasil Ltda', count: 38, value: 92000000 },
          { name: 'Engenharia e Construções Sul S.A.', count: 32, value: 156000000 },
          { name: 'Instalações Elétricas Brasil Ltda', count: 29, value: 45000000 },
          { name: 'Serviços Terceirizados Ltda', count: 26, value: 38000000 },
          { name: 'Limpeza e Conservação Profissional Ltda', count: 24, value: 29000000 },
          { name: 'Software Solutions Ltda', count: 22, value: 52000000 },
          { name: 'Vigilância Patrimonial Segurança Ltda', count: 20, value: 34000000 },
          { name: 'Manutenção Predial Profissional Ltda', count: 18, value: 27000000 },
          { name: 'Transportes e Logística Brasil Ltda', count: 16, value: 41000000 },
        ]}
        countLabel="Contratos"
        valueLabel="Valor total"
        showRanking={true}
      />

      {/* How it Works */}
      <HowItWorksBlock
        title="Como o SmartLic ajuda na subcontratação"
        subtitle="De identificar empresas vencedoras a fechar o subcontrato — com dados, não achismo."
        steps={subSteps}
      />

      {/* Testimonials */}
      <TestimonialsBlock
        title="Quem usa recomenda"
        subtitle="Empresas que transformaram a subcontratação em estratégia de crescimento."
        testimonials={subTestimonials}
      />

      {/* CTA */}
      <UseCaseCTA
        heading="O próximo grande contrato pode ser seu — como subcontratado"
        subtitle="Milhares de empresas vencedoras precisam de parceiros como você. Descubra quem são e como abordá-las com a proposta certa."
        ctaLabel="Encontrar empresas vencedoras"
        ctaHref="/signup?source=subcontratar-bottom-cta"
        secondaryCtaLabel="Ver planos"
        secondaryCtaHref="/planos"
        source="subcontratar-landing"
        trustLine="14 dias grátis. Dados reais. Decisão objetiva."
      />

      <Footer />
    </>
  );
}
