/**
 * Intent Landing Page: /para-consultorias
 *
 * CONV-007-1: Landing page de intenção investigativa — conecta consultorias
 * e assessorias à plataforma SmartLic. Cluster: investigativa.
 *
 * Server component. Metadata + JSON-LD via IntentLandingPage.
 */
import type { Metadata } from 'next';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import IntentLandingPage from '@/app/components/IntentLandingPage';

export const revalidate = 3600;

export const metadata: Metadata = {
  title: 'Para Consultorias — Dados de licitação para seus clientes | SmartLic',
  description:
    'Relatórios detalhados e análises setoriais para consultorias e assessorias de licitação. Acesse dados históricos e tendências do mercado público.',
  alternates: {
    canonical: 'https://smartlic.tech/para-consultorias',
  },
  openGraph: {
    title: 'Para Consultorias — Dados de licitação para seus clientes | SmartLic',
    description:
      'Relatórios detalhados e análises setoriais para consultorias e assessorias de licitação.',
    url: 'https://smartlic.tech/para-consultorias',
    type: 'website',
    locale: 'pt_BR',
  },
  robots: { index: true, follow: true },
};

export default function ParaConsultoriasPage() {
  return (
    <>
      <LandingNavbar />
      <IntentLandingPage
        cluster="investigativa"
        headline="Dados de licitação para seus clientes"
        subtitle="Relatórios detalhados e análises setoriais para consultorias e assessorias. Dados reais das fontes oficiais."
        steps={[
          {
            title: 'Escolha o setor do cliente',
            description:
              'Selecione entre 20 setores da economia. O sistema busca editais, contratos e fornecedores do segmento desejado.',
          },
          {
            title: 'Acesse dados históricos e tendências',
            description:
              'Analise histórico de concorrências, compare preços e mapeie tendências do mercado público com dados reais.',
          },
          {
            title: 'Gere relatórios profissionais',
            description:
              'Exporte relatórios em Excel e PDF com análise setorial completa. Relatórios prontos para entregar ao cliente.',
          },
        ]}
        socialProofText="+10 mil relatórios gerados para consultorias em todo Brasil. Dados consolidados das principais fontes oficiais."
        ctaPrimary={{
          text: 'Comprar relatório avulso',
          href: '/checkout?sku=relatorio-setorial',
        }}
        ctaSecondary={{ text: 'Explorar dados abertos', href: '/observatorio' }}
        pageTitle="Para Consultorias — Dados de licitação para seus clientes | SmartLic"
        pageDescription="Relatórios detalhados e análises setoriais para consultorias e assessorias de licitação. Acesse dados históricos e tendências do mercado público."
      />
      <Footer />
    </>
  );
}
