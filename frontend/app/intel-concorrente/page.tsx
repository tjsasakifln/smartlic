/**
 * COMPINT-010 (#1662): Competitive Intelligence Flagship Page.
 *
 * Mapa de Territorio Competitivo — /intel-concorrente
 * Auth-gated page with competitive intel capability check.
 */
import type { Metadata } from 'next';
import { redirect } from 'next/navigation';
import { createServerComponentClient } from '@supabase/auth-helpers-nextjs';
import { cookies } from 'next/headers';
import LandingNavbar from '@/app/components/landing/LandingNavbar';
import Footer from '@/app/components/Footer';
import IntelConcorrenteClient from './IntelConcorrenteClient';

export const revalidate = 0; // Dynamic page

export const metadata: Metadata = {
  title: 'Inteligencia Concorrencial — Mapa de Territorio | SmartLic',
  description:
    'Analise concorrentes em licitacoes publicas. Mapa de territorio, market share, benchmarks setoriais e dossie completo de fornecedores B2G.',
  robots: { index: false, follow: false },
};

export default async function IntelConcorrentePage() {
  // Check auth server-side
  const supabase = createServerComponentClient({ cookies });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    redirect('/login?redirect=/intel-concorrente');
  }

  return (
    <>
      <LandingNavbar />
      <IntelConcorrenteClient />
      <Footer />
    </>
  );
}
