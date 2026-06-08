/**
 * Intent Landing Page: /para-fornecedores
 *
 * CONV-007-1: Landing page de intenção de subcontratação — conecta
 * fornecedores terceiros a oportunidades em licitações. Cluster: subcontratacao.
 *
 * Server component. Metadata + JSON-LD via IntentLandingPage.
 */
import type { Metadata } from 'next';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import IntentLandingPage from '@/app/components/IntentLandingPage';

export const revalidate = 3600;

export const metadata: Metadata = {
  title:
    'Para Fornecedores — Seja subcontratado em licitações | SmartLic',
  description:
    'Identifique consórcios, subcontratações e oportunidades para sua empresa atuar como fornecedor terceiro em licitações públicas.',
  alternates: {
    canonical: 'https://smartlic.tech/para-fornecedores',
  },
  openGraph: {
    title:
      'Para Fornecedores — Seja subcontratado em licitações | SmartLic',
    description:
      'Identifique consórcios, subcontratações e oportunidades para sua empresa atuar como fornecedor terceiro em licitações.',
    url: 'https://smartlic.tech/para-fornecedores',
    type: 'website',
    locale: 'pt_BR',
  },
  robots: { index: true, follow: true },
};

export default function ParaFornecedoresPage() {
  return (
    <>
      <LandingNavbar />
      <IntentLandingPage
        cluster="subcontratacao"
        headline="Seja subcontratado em licitações"
        subtitle="Identifique consórcios, subcontratações e oportunidades para sua empresa atuar como fornecedor terceiro."
        steps={[
          {
            title: 'Identifique oportunidades',
            description:
              'Descubra empresas que venceram licitações e buscam fornecedores terceiros para atender contratos públicos.',
          },
          {
            title: 'Conecte-se com vencedores',
            description:
              'Mapeie as empresas vencedoras de licitações no seu setor. Entenda as necessidades de cada contrato.',
          },
          {
            title: 'Feche parcerias',
            description:
              'Ofereça seus produtos ou serviços como subcontratado. Receba alertas de novas oportunidades de parceria.',
          },
        ]}
        socialProofText="Milhares de pontes de subcontratação mapeadas entre fornecedores e vencedores de licitações em todo Brasil."
        ctaPrimary={{
          text: 'Mapear pontes de subcontratação',
          href: '/subcontratacao',
        }}
        ctaSecondary={{ text: 'Ver editais recentes', href: '/licitacoes' }}
        pageTitle="Para Fornecedores — Seja subcontratado em licitações | SmartLic"
        pageDescription="Identifique consórcios, subcontratações e oportunidades para sua empresa atuar como fornecedor terceiro em licitações."
      />
      <Footer />
    </>
  );
}
