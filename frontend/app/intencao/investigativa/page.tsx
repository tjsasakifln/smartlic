/**
 * Intent landing page — Investigativa (orgao/contrato)
 *
 * Route: /intencao/investigativa
 * Users arrive via IntentRouter (#1511) when searching for orgaos
 * compradores, contratos publicos, or deep market research.
 */
import type { Metadata } from 'next';
import IntentLandingPage from '../../components/IntentLandingPage';
import IntentLandingLayout from '../IntentLandingLayout';

export const metadata: Metadata = {
  title: 'Pesquisa de Licitações e Mercado Público — SmartLic',
  description:
    'Mapeie órgãos compradores, analise contratos, encontre oportunidades de pesquisa com dados oficiais do governo.',
};

export default function InvestigativaPage() {
  return (
    <IntentLandingLayout>
      <IntentLandingPage
        cluster="investigativa"
        headline="Pesquise licitações com profundidade"
        subtitle="Mapeie órgãos compradores, analise contratos, encontre oportunidades de pesquisa"
        steps={[
          {
            title: '50 mil+ órgãos públicos mapeados',
            description:
              'Selecione órgãos, municípios ou esferas governamentais e acesse todo o histórico de contratações e gastos públicos.',
          },
          {
            title: 'R$ 1 bilhão+ em contratos analisados',
            description:
              'Identifique tendências de compra, sazonalidades e padrões de gasto por setor, região e modalidade.',
          },
          {
            title: 'Relatórios setoriais completos',
            description:
              'Gere diagnósticos detalhados com dados consolidados, gráficos e insights estratégicos para sua pesquisa.',
          },
        ]}
        socialProofText="SmartLic processa mais de 2 milhões de contratos públicos com atualização diária, permitindo pesquisas profundas e análises de mercado em todo o Brasil."
        ctaPrimary={{
          text: 'Mapa de oportunidades — R$47',
          href: '/checkout?sku=mapa-oportunidades',
        }}
        ctaSecondary={{
          text: 'Relatório setorial →',
          href: '/checkout?sku=relatorio-setorial',
        }}
        pageTitle="Pesquisa de Licitações e Mercado Público — SmartLic"
        pageDescription="Mapeie órgãos compradores, analise contratos, encontre oportunidades de pesquisa com dados oficiais do governo."
      />
    </IntentLandingLayout>
  );
}
