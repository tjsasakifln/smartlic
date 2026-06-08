/**
 * Intent Landing Page: /para-advogados
 *
 * CONV-007-1: Landing page de intenção jurídica — conecta advogados e
 * profissionais do direito licitatório à plataforma SmartLic. Cluster: juridica.
 *
 * Server component. Metadata + JSON-LD via IntentLandingPage.
 */
import type { Metadata } from 'next';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import IntentLandingPage from '@/app/components/IntentLandingPage';

export const revalidate = 3600;

export const metadata: Metadata = {
  title: 'Para Advogados — Impugnação de editais com dados | SmartLic',
  description:
    'Acesse editais completos, jurisprudência e análise detalhada para embasar seus recursos e impugnações.',
  alternates: {
    canonical: 'https://smartlic.tech/para-advogados',
  },
  openGraph: {
    title: 'Para Advogados — Impugnação de editais com dados | SmartLic',
    description:
      'Acesse editais completos, jurisprudência e análise detalhada para embasar recursos e impugnações.',
    url: 'https://smartlic.tech/para-advogados',
    type: 'website',
    locale: 'pt_BR',
  },
  robots: { index: true, follow: true },
};

export default function ParaAdvogadosPage() {
  return (
    <>
      <LandingNavbar />
      <IntentLandingPage
        cluster="juridica"
        headline="Fundamentação jurídica para licitações"
        subtitle="Acesse editais completos, jurisprudência e análise detalhada para embasar seus recursos e impugnações."
        steps={[
          {
            title: 'Busque o edital',
            description:
              'Encontre o edital completo que você precisa analisar. Busca inteligente nas bases oficiais com dados estruturados.',
          },
          {
            title: 'Analise cláusulas e jurisprudência',
            description:
              'Examine cada cláusula com dados de jurisprudência relacionada. Identifique pontos passíveis de impugnação.',
          },
          {
            title: 'Prepare sua impugnação ou recurso',
            description:
              'Use os dados do sistema para fundamentar seus recursos com argumentos sólidos e jurisprudência atualizada.',
          },
        ]}
        socialProofText="Base de conhecimento jurídico com milhares de editais e decisões. Dados oficiais para embasar sua atuação."
        ctaPrimary={{
          text: 'Começar trial grátis',
          href: '/signup?source=intent-juridica',
        }}
        ctaSecondary={{ text: 'Ver base legal', href: '/compliance' }}
        pageTitle="Para Advogados — Impugnação de editais com dados | SmartLic"
        pageDescription="Acesse editais completos, jurisprudência e análise detalhada para embasar seus recursos e impugnações."
      />
      <Footer />
    </>
  );
}
