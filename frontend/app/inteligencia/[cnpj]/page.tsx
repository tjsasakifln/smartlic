/**
 * VITRINE-001 (#1612): Public Intelligence Vitrine page /inteligencia/[cnpj].
 *
 * SEO programmatic page showing aggregated public contract data for a company.
 * ISR 1h. No auth required. Drives organic acquisition.
 *
 * B2G equivalent of Glassdoor salaries or SimilarWeb traffic.
 */

import { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import { getBackendUrl } from '@/lib/backend-url';
import { buildCanonical, buildOperationalTitle, buildOperationalDescription } from '@/lib/seo';
import { ssgLimitedFetch } from '@/lib/concurrency';
import EmptyStateSEO from '@/components/seo/EmptyStateSEO';
import IntelVitrineClient from './IntelVitrineClient';
import { CompanyOverview } from './components/CompanyOverview';
import { PublicContractsList } from './components/PublicContractsList';
import { SectorPosition } from './components/SectorPosition';

const BACKEND_URL = getBackendUrl();

// VITRINE-001: ISR 1h — dados públicos atualizados 3x/semana
export const revalidate = 3600;

export function generateStaticParams() {
  return []; // SSR on-demand via sitemap
}

// ---------------------------------------------------------------------------
// Tipos
// ---------------------------------------------------------------------------

export interface OrgaoInfoVitrine {
  nome: string;
  cnpj: string;
  total_contratos: number;
  valor_total: number;
}

export interface DistribuicaoItemVitrine {
  chave: string;
  quantidade: number;
  valor_total: number;
}

export interface RankingInfoVitrine {
  percentil: number;
  posicao: number;
  total_empresas_setor: number;
  texto_contexto: string;
}

export interface IntelVitrineData {
  cnpj: string;
  razao_social: string;
  nome_fantasia: string | null;
  setor_principal: string | null;
  setor_nome: string | null;
  total_contratos_12m: number;
  valor_total_12m: number;
  total_contratos_alltime: number;
  valor_total_alltime: number;
  ranking: RankingInfoVitrine | null;
  top_orgaos: OrgaoInfoVitrine[];
  distribuicao_uf: DistribuicaoItemVitrine[];
  distribuicao_ano: DistribuicaoItemVitrine[];
  distribuicao_modalidade: DistribuicaoItemVitrine[];
  generated_at: string;
  aviso_legal: string;
}

// ---------------------------------------------------------------------------
// Data fetching
// ---------------------------------------------------------------------------

async function fetchVitrine(cnpj: string): Promise<IntelVitrineData | null> {
  const cnpjClean = cnpj.replace(/\D/g, '');
  if (cnpjClean.length !== 14) return null;

  try {
    const resp = await ssgLimitedFetch(
      `${BACKEND_URL}/v1/intel/vitrine/${cnpjClean}`,
      {
        next: { revalidate: 3600 },
        signal: AbortSignal.timeout(15_000),
      },
    );
    if (resp.status >= 500) {
      throw new Error(`intel_vitrine_backend_5xx:${resp.status}`);
    }
    if (!resp.ok) return null;
    return await resp.json();
  } catch (err) {
    if (err instanceof Error && err.message.startsWith('intel_vitrine_backend_5xx')) {
      throw err;
    }
    return null;
  }
}

// ---------------------------------------------------------------------------
// SEO Metadata
// ---------------------------------------------------------------------------

type Props = { params: Promise<{ cnpj: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { cnpj } = await params;
  const vitrine = await fetchVitrine(cnpj);

  if (!vitrine) {
    return {
      title: 'Inteligência de Contratos Públicos — SmartLic',
      description: 'Veja dados agregados de contratos públicos por CNPJ. Rankings, órgãos compradores e tendências.',
      robots: { index: false, follow: true },
      alternates: { canonical: buildCanonical(`/inteligencia/${cnpj}`) },
    };
  }

  const valorFmt = vitrine.valor_total_12m >= 1_000_000
    ? `R$ ${(vitrine.valor_total_12m / 1_000_000).toFixed(1)} mi`
    : `R$ ${(vitrine.valor_total_12m / 1_000).toFixed(0)} mil`;

  const title = buildOperationalTitle('inteligencia', {
    subject: vitrine.razao_social,
    count: vitrine.total_contratos_12m,
    value: valorFmt,
  });

  const description = vitrine.ranking
    ? `${vitrine.razao_social} ganhou ${valorFmt} em contratos públicos nos últimos 12 meses. ${vitrine.ranking.texto_contexto}`
    : `${vitrine.razao_social} — ${vitrine.total_contratos_alltime} contratos públicos registrados. Veja ranking, principais clientes e tendências.`;

  return {
    title,
    description,
    alternates: { canonical: buildCanonical(`/inteligencia/${cnpj}`) },
    openGraph: {
      title: `${vitrine.razao_social} — Contratos Públicos Inteligência`,
      description: `${vitrine.total_contratos_12m} contratos (12m) | ${valorFmt}`,
      url: buildCanonical(`/inteligencia/${cnpj}`),
      type: 'website',
      locale: 'pt_BR',
    },
    twitter: {
      card: 'summary_large_image',
      title: `${vitrine.razao_social} — Inteligência de Contratos Públicos`,
      description: `${vitrine.total_contratos_12m} contratos | ${valorFmt}`,
    },
    robots: {
      index: vitrine.total_contratos_alltime > 0,
      follow: true,
    },
  };
}

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default async function IntelVitrinePage({ params }: Props) {
  const { cnpj } = await params;
  const cnpjClean = cnpj.replace(/\D/g, '');

  // Validação de formato
  if (cnpjClean.length !== 14) {
    notFound(); // adr-seo-001-allow: invalid CNPJ format
  }

  const vitrine = await fetchVitrine(cnpjClean);

  // ADR-SEO-001: data absence → EmptyStateSEO (not notFound)
  if (!vitrine) {
    return (
      <EmptyStateSEO
        title="CNPJ sem dados de contratos públicos"
        description="Este CNPJ não possui contratos públicos registrados nas fontes oficiais no momento. Os dados são indexados periodicamente — volte em breve."
        ctaHref="/inteligencia"
        ctaLabel="Consultar outro CNPJ"
      />
    );
  }

  // Format helpers
  const formatBRL = (value: number): string => {
    if (value >= 1_000_000_000) {
      return `R$ ${(value / 1_000_000_000).toLocaleString('pt-BR', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })} bi`;
    }
    if (value >= 1_000_000) {
      return `R$ ${(value / 1_000_000).toLocaleString('pt-BR', {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })} mi`;
    }
    if (value >= 1_000) {
      return `R$ ${(value / 1_000).toLocaleString('pt-BR', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0,
      })} mil`;
    }
    return value.toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    });
  };

  // JSON-LD: Dataset schema
  const datasetSchema = {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: `Contratos Públicos — ${vitrine.razao_social}`,
    description: `Dados agregados de contratos públicos de ${vitrine.razao_social} (CNPJ ${cnpjMasked}). ${vitrine.total_contratos_alltime} contratos, totalizando ${formatBRL(vitrine.valor_total_alltime)}.`,
    creator: { '@type': 'Organization', name: 'SmartLic', url: 'https://smartlic.tech' },
    license: 'https://dados.gov.br/dados/conteudo/sobre-dados-abertos',
    distribution: {
      '@type': 'DataDownload',
      contentUrl: `https://smartlic.tech/inteligencia/${cnpjClean}`,
      encodingFormat: 'text/html',
    },
  };

  return (
    <div className="min-h-screen flex flex-col bg-canvas">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(datasetSchema) }}
      />

      <main className="flex-1">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
          {/* ===== Breadcrumb ===== */}
          <nav className="flex items-center gap-2 text-sm text-ink-secondary mb-6 flex-wrap">
            <Link href="/" className="hover:text-brand-blue transition-colors">
              Início
            </Link>
            <span>/</span>
            <Link href="/inteligencia" className="hover:text-brand-blue transition-colors">
              Inteligência Pública
            </Link>
            <span>/</span>
            <span className="text-ink truncate max-w-[250px]">
              {vitrine.razao_social}
            </span>
          </nav>

          {/* ===== Hero Section ===== */}
          <CompanyOverview vitrine={vitrine} cnpjClean={cnpjClean} formatBRL={formatBRL} />

          {/* ===== Ranking Card ===== */}
          <SectorPosition vitrine={vitrine} />

          {/* ===== Charts Section (Client Component) ===== */}
          <IntelVitrineClient vitrine={vitrine} formatBRL={formatBRL} />

          {/* ===== Top Orgaos ===== */}
          <PublicContractsList vitrine={vitrine} formatBRL={formatBRL} />

          {/* ===== CTA Section ===== */}
          <section className="mb-10 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-700 p-6 sm:p-8 text-center">
            <h2 className="text-xl sm:text-2xl font-bold text-white mb-2">
              Veja dados completos e alertas para este CNPJ
            </h2>
            <p className="text-blue-100 mb-6 max-w-lg mx-auto">
              O SmartLic monitora editais e contratos públicos em tempo real.
              Receba alertas personalizados e análises exclusivas.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <Link
                href={`/signup?ref=vitrine-${cnpjClean}&utm_source=pseo&utm_medium=organic&utm_content=vitrine_cta`}
                className="inline-block px-6 py-3 bg-white text-blue-700 font-semibold rounded-lg hover:bg-blue-50 transition-colors min-h-[44px] leading-[44px] sm:leading-normal sm:py-3"
              >
                Teste grátis por 14 dias
              </Link>
              <Link
                href={`/cnpj/${cnpjClean}`}
                className="inline-block px-6 py-3 bg-blue-500 text-white font-semibold rounded-lg hover:bg-blue-400 transition-colors min-h-[44px] leading-[44px] sm:leading-normal sm:py-3"
              >
                Ver perfil completo
              </Link>
            </div>
            <p className="text-xs text-blue-200 mt-3">
              Sem cartão de crédito &middot; 14 dias grátis
            </p>
          </section>

          {/* ===== Internal Links ===== */}
          <section className="mb-10">
            <h2 className="text-lg font-semibold text-ink mb-4">
              Veja também
            </h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <Link
                href={`/fornecedores/${cnpjClean}`}
                className="p-3 rounded-lg border border-[var(--border)] text-sm text-brand-blue hover:bg-surface-1 transition-colors text-center"
              >
                Perfil de Fornecedor
              </Link>
              <Link
                href={`/cnpj/${cnpjClean}`}
                className="p-3 rounded-lg border border-[var(--border)] text-sm text-brand-blue hover:bg-surface-1 transition-colors text-center"
              >
                Consulta CNPJ
              </Link>
              <Link
                href="/licitacoes"
                className="p-3 rounded-lg border border-[var(--border)] text-sm text-brand-blue hover:bg-surface-1 transition-colors text-center"
              >
                Licitações por Setor
              </Link>
              <Link
                href="/dados"
                className="p-3 rounded-lg border border-[var(--border)] text-sm text-brand-blue hover:bg-surface-1 transition-colors text-center"
              >
                Dados Públicos
              </Link>
            </div>
          </section>

          {/* ===== Aviso Legal ===== */}
          <p className="text-xs text-ink-secondary italic">
            {vitrine.aviso_legal}
          </p>
        </div>
      </main>
    </div>
  );
}
