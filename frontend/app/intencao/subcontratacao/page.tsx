/**
 * Intent landing page — Subcontratacao (subcontracting/partnership)
 *
 * Route: /intencao/subcontratacao
 * Users arrive via IntentRouter (#1511) when searching for subcontracting,
 * consorcios, or partnership opportunities in public bidding.
 */
import type { Metadata } from 'next';
import IntentLandingPage from '../../components/IntentLandingPage';
import IntentLandingLayout from '../IntentLandingLayout';

export const metadata: Metadata = {
  title: 'Subcontratação em Licitações — SmartLic',
  description:
    'Seja subcontratado por vencedores de licitação, forme consórcios e expanda suas oportunidades no mercado público.',
};

export default function SubcontratacaoPage() {
  return (
    <IntentLandingLayout>
      <IntentLandingPage
        cluster="subcontratacao"
        headline="Encontre parceiros de licitação"
        subtitle="Seja subcontratado por vencedores de licitação, forme consórcios e expanda suas oportunidades"
        steps={[
          {
            title: '5 mil+ empresas parceiras cadastradas',
            description:
              'Cadastre sua empresa e seja encontrado por vencedores de licitação que precisam de subcontratados qualificados.',
          },
          {
            title: '27 estados com oportunidades',
            description:
              'Descubra editais que preveem subcontratação obrigatória em todas as regiões do Brasil.',
          },
          {
            title: 'Match inteligente com vencedores',
            description:
              'Nosso algoritmo conecta sua empresa a fornecedores que venceram licitações e precisam de parceiros para execução.',
          },
        ]}
        socialProofText="Empresas subcontratadas faturam em média R$ 150 mil por contrato. O SmartLic conecta fornecedores a vencedores de licitação em todo o Brasil."
        ctaPrimary={{
          text: 'Matching + Relatório — R$97',
          href: '/checkout?sku=relatorio-subcontratacao',
        }}
        ctaSecondary={{
          text: 'Ver editais recentes →',
          href: '/licitacoes',
        }}
        pageTitle="Subcontratação em Licitações — SmartLic"
        pageDescription="Seja subcontratado por vencedores de licitação, forme consórcios e expanda suas oportunidades no mercado público."
      />
    </IntentLandingLayout>
  );
}
