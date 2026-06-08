/**
 * Intent landing page — Comercial (fornecedor/CNPJ)
 *
 * Route: /intencao/comercial
 * Users arrive via IntentRouter (#1511) when searching for fornecedores,
 * CNPJs, or commercial opportunities in public bidding.
 */
import type { Metadata } from 'next';
import IntentLandingPage from '../../components/IntentLandingPage';
import IntentLandingLayout from '../IntentLandingLayout';

export const metadata: Metadata = {
  title: 'Inteligência Comercial B2G — SmartLic',
  description:
    'Encontre fornecedores, analise concorrentes e descubra quem vence licitações públicas. Plataforma de inteligência B2G com dados oficiais do governo.',
};

export default function ComercialPage() {
  return (
    <IntentLandingLayout>
      <IntentLandingPage
        cluster="comercial"
        headline="Venda para o governo com inteligência"
        subtitle="Encontre fornecedores, analise concorrentes, descubra quem vence licitações públicas"
        steps={[
          {
            title: '2 milhões de contratos monitorados',
            description:
              'Busque por CNPJ ou setor e acesse dados completos de fornecedores que já vendem para o governo em todo o Brasil.',
          },
          {
            title: '27 estados com cobertura nacional',
            description:
              'Compare preços, margens e histórico de contratações em qualquer região do país com dados atualizados diariamente.',
          },
          {
            title: '15+ setores classificados por IA',
            description:
              'Receba alertas de oportunidades filtradas automaticamente para o seu segmento de atuação.',
          },
        ]}
        socialProofText="Empresas que usam o SmartLic aumentam em até 3x suas chances de vencer licitações públicas. Mais de 2 mil usuários ativos em todo o Brasil monitoram oportunidades com nossa plataforma."
        ctaPrimary={{
          text: 'Relatório de fornecedor — R$67',
          href: '/checkout?sku=relatorio-fornecedor',
        }}
        ctaSecondary={{
          text: 'Monitoramento de editais →',
          href: '/signup?source=intent-comercial',
        }}
        pageTitle="Inteligência Comercial B2G — SmartLic"
        pageDescription="Encontre fornecedores, analise concorrentes e descubra quem vence licitações públicas. Plataforma de inteligência B2G com dados oficiais do governo."
      />
    </IntentLandingLayout>
  );
}
