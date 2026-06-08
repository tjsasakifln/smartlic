/**
 * Flagship Landing Page: /subcontratacao
 *
 * REV-005 Step 5 (#1317): Subcontratacao flagship page with R$97 CTA.
 * Converte intencao de subcontratacao em compra do produto subcontratacao-map.
 *
 * Server component. Metadata + JSON-LD via static generation.
 */
import type { Metadata } from 'next';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import SubcontratacaoClient from './SubcontratacaoClient';

export const revalidate = 3600;

export const metadata: Metadata = {
  title:
    'Subcontratacao em Licitacoes — Encontre Oportunidades B2G | SmartLic',
  description:
    'Identifique pontes de subcontratacao em licitacoes publicas. Descubra empresas vencedoras que precisam de fornecedores para contratos publicos.',
  alternates: {
    canonical: 'https://smartlic.tech/subcontratacao',
  },
  openGraph: {
    title:
      'Subcontratacao em Licitacoes — Encontre Oportunidades | SmartLic',
    description:
      'Identifique pontes de subcontratacao em licitacoes publicas e conecte sua empresa a oportunidades B2G.',
    url: 'https://smartlic.tech/subcontratacao',
    type: 'website',
    locale: 'pt_BR',
    siteName: 'SmartLic',
  },
  robots: { index: true, follow: true },
};

export default function SubcontratacaoPage() {
  return (
    <>
      <LandingNavbar />
      <SubcontratacaoClient />
      <Footer />
    </>
  );
}
