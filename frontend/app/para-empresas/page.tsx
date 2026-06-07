/**
 * Intent Landing Page: /para-empresas
 *
 * CONV-007-1: Landing page de intenção comercial — conecta empresas B2G
 * à plataforma SmartLic. Cluster: comercial.
 *
 * Server component. Metadata + JSON-LD via IntentLandingPage.
 */
import type { Metadata } from 'next';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import IntentLandingPage from '@/app/components/IntentLandingPage';

export const revalidate = 3600;

export const metadata: Metadata = {
  title: 'Para Empresas — Encontre editais para sua empresa | SmartLic',
  description:
    'Descubra editais classificados por setor com análise de viabilidade. Aumente suas chances de vencer licitações.',
  alternates: {
    canonical: 'https://smartlic.tech/para-empresas',
  },
  openGraph: {
    title: 'Para Empresas — Encontre editais para sua empresa | SmartLic',
    description:
      'Descubra editais classificados por setor com análise de viabilidade. Aumente suas chances de vencer licitações.',
    url: 'https://smartlic.tech/para-empresas',
    type: 'website',
    locale: 'pt_BR',
  },
  robots: { index: true, follow: true },
};

export default function ParaEmpresasPage() {
  return (
    <>
      <LandingNavbar />
      <IntentLandingPage
        cluster="comercial"
        headline="Encontre editais para sua empresa"
        subtitle="IA classifica automaticamente licitações do seu setor. Economize horas de pesquisa manual."
        steps={[
          {
            title: 'Defina seu setor',
            description:
              'Selecione seu ramo de atuação entre 20 setores. O sistema entende seu nicho e busca editais compatíveis.',
          },
          {
            title: 'Receba editais classificados',
            description:
              'IA analisa e classifica cada edital com análise de viabilidade em 4 fatores. Você só vê o que importa.',
          },
          {
            title: 'Organize seu pipeline',
            description:
              'Arraste editais no kanban e foque no que importa. Acompanhe propostas em andamento com alertas inteligentes.',
          },
        ]}
        socialProofText="+1.5 milhão de editais monitorados para empresas de todos os portes. Dados reais das fontes oficiais (PNCP, PCP, ComprasGov)."
        ctaPrimary={{ text: 'Começar trial grátis', href: '/signup?source=intent-comercial' }}
        ctaSecondary={{ text: 'Ver exemplos de resultados', href: '/buscar' }}
        pageTitle="Para Empresas — Encontre editais para sua empresa | SmartLic"
        pageDescription="Descubra editais classificados por setor com análise de viabilidade. Aumente suas chances de vencer licitações."
      />
      <Footer />
    </>
  );
}
