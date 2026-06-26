/**
 * STORY-431 AC1+AC3+AC4+AC5+AC7+AC13+AC14: Observatory monthly report page.
 *
 * Slug format: raio-x-abril-2026 → mes=4, ano=2026
 * Renders charts (BarChart, PieChart, LineChart), CSV download, embed button.
 *
 * AC13: notFound() on malformed slug only; generateMetadata returns
 * robots:noindex when data is missing/empty.
 * AC14: Sentry.captureMessage when relatorio is empty (warning level + tags).
 *
 * Issue #1034 (HOTFIX): Removed `notFound()` for null/empty backend payloads.
 * Under ISR (revalidate=86400), `notFound()` becomes a 24h terminal state from
 * a single transient blip. Now: transient errors re-throw (preserve last-good
 * ISR cache); empty-period payloads render <EmptyStateSEO> with noindex.
 */

import { Metadata } from 'next';
import Link from 'next/link';
import { notFound } from 'next/navigation';
import * as Sentry from '@sentry/nextjs';
import { fetchWithBudget } from '@/lib/safe-fetch';
import { buildCanonical } from '@/lib/seo';
import ObservatorioRelatorioClient from './ObservatorioRelatorioClient';
import { FoundersRibbon } from '@/components/banners/FoundersRibbon';
import EmptyStateSEO from '@/components/seo/EmptyStateSEO';
import { EmbedIntelFeed } from '@/components/pseo/EmbedIntelFeed';

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

const MONTH_NAMES_PT: Record<string, number> = {
  janeiro: 1, fevereiro: 2, marco: 3, abril: 4, maio: 5, junho: 6,
  julho: 7, agosto: 8, setembro: 9, outubro: 10, novembro: 11, dezembro: 12,
};

const MONTH_NAMES_DISPLAY: Record<number, string> = {
  1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
  7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro',
};

function parseSlug(slug: string): { mes: number; ano: number } | null {
  // Expected: "raio-x-{mes_nome}-{ano}" e.g. "raio-x-marco-2026"
  const parts = slug.split('-');
  if (parts.length < 4) return null;
  const mesNome = parts[parts.length - 2];
  const anoStr = parts[parts.length - 1];
  const mes = MONTH_NAMES_PT[mesNome.toLowerCase()];
  const ano = parseInt(anoStr, 10);
  if (!mes || isNaN(ano) || ano < 2024) return null;
  return { mes, ano };
}

/**
 * PSEO-P1-2048: Migrado para fetchWithBudget com throwOn5xx: true.
 * Dois comportamentos:
 *   - 2xx + empty payload: retorna parsed (page decide via total_editais).
 *   - 4xx (incl. 404): retorna null via fetchWithBudget (fallback default).
 *   - 5xx ISR: throw (preserva stale cache).
 *   - 5xx build: retorna null (nao quebra build).
 */
async function fetchRelatorio(mes: number, ano: number): Promise<any> {
  return fetchWithBudget(
    `${BACKEND_URL}/v1/observatorio/relatorio/${mes}/${ano}`,
    {
      timeout: 15000,
      retries: 1,
      revalidate: 3600, // 1h ISR — SEO-FE-ISR-001 (#1038)
      throwOn5xx: true,
      label: 'observatorio-relatorio',
    },
  );
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const parsed = parseSlug(slug);
  // STORY-431 AC13: malformed slug → noindex metadata (page itself returns 404).
  if (!parsed) {
    return {
      title: 'Relatório não encontrado',
      robots: { index: false, follow: false },
      alternates: { canonical: buildCanonical(`/observatorio/${slug}`) },
    };
  }

  const { mes, ano } = parsed;
  const mesDisplay = MONTH_NAMES_DISPLAY[mes] ?? String(mes);
  // Issue #1034: swallow transient throws in metadata phase — we still want
  // to ship a (noindex) <head> for the EmptyStateSEO render below.
  let relatorio: any = null;
  try {
    relatorio = await fetchRelatorio(mes, ano);
  } catch {
    relatorio = null;
  }

  // STORY-431 AC13 + Issue #1034: missing or empty payload → noindex metadata so an
  // accidentally-cached blank page never lands in Google's index.
  // Issue #658: explicit canonical to own URL (não herdar root do layout.tsx).
  if (!relatorio || !relatorio.total_editais) {
    return {
      title: `Raio-X das Licitações — ${mesDisplay} ${ano}`,
      description: `Análise mensal das licitações públicas brasileiras em ${mesDisplay.toLowerCase()} de ${ano}.`,
      alternates: { canonical: `https://smartlic.tech/observatorio/${slug}` },
      robots: { index: false, follow: true },
    };
  }

  const totalDisplay = new Intl.NumberFormat('pt-BR').format(relatorio.total_editais);
  const title = `${totalDisplay} editais em ${mesDisplay} de ${ano} — Raio-X das Licitações`;
  const description = `O Brasil publicou ${totalDisplay} editais nas fontes oficiais em ${mesDisplay.toLowerCase()} de ${ano}. Análise completa por UF, modalidade e setor com dados reais. Licença Creative Commons BY 4.0.`;

  return {
    title,
    description,
    alternates: { canonical: `https://smartlic.tech/observatorio/${slug}` },
    openGraph: {
      title,
      description,
      url: `https://smartlic.tech/observatorio/${slug}`,
      type: 'article',
      locale: 'pt_BR',
      images: [
        {
          url: `/api/og?title=${encodeURIComponent(`Raio-X ${mesDisplay} ${ano}`)}&subtitle=${encodeURIComponent(`${totalDisplay} editais publicados nas fontes oficiais`)}`,
          width: 1200,
          height: 630,
          alt: `Raio-X das Licitações — ${mesDisplay} ${ano} | SmartLic`,
        },
      ],
    },
    robots: { index: true },
  };
}

export default async function RelatorioPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  // STORY-431 AC13: malformed slug → 404 (page itself, plus noindex metadata).
  const parsed = parseSlug(slug);
  if (!parsed) notFound(); // adr-seo-001-allow: slug fails raio-x-{mes}-{ano} format — not a valid observatorio period

  const { mes, ano } = parsed;
  const mesDisplay = MONTH_NAMES_DISPLAY[mes] ?? String(mes);
  // Issue #1034: NEVER call notFound() here. Transient throws bubble up so ISR
  // preserves the last-good cache; null payloads (4xx) and empty periods render
  // <EmptyStateSEO> with noindex metadata (set in generateMetadata above).
  const relatorio = await fetchRelatorio(mes, ano);

  if (!relatorio || !Number(relatorio.total_editais ?? 0)) {
    Sentry.captureMessage('observatorio_empty_period', {
      level: 'warning',
      tags: { mes: String(mes), ano: String(ano), slug, render: 'empty_state' },
    });
    return (
      <EmptyStateSEO
        title={`Raio-X das Licitações — ${mesDisplay} ${ano}`}
        description={`Ainda não temos um relatório consolidado para ${mesDisplay.toLowerCase()} de ${ano}. Os dados são publicados conforme o PNCP processa os editais do período. Volte em breve ou explore outros meses do observatório.`}
        ctaHref="/observatorio"
        ctaLabel="Ver outros meses do observatório"
        periodLabel={`${mesDisplay} de ${ano}`}
      />
    );
  }

  const totalEditais = Number(relatorio.total_editais ?? 0);
  const periodoNonEmpty = typeof relatorio.periodo === 'string' && relatorio.periodo.trim().length > 0;

  // STORY-431 AC14 + Issue #1034: empty-period Sentry warning is now emitted
  // inside the early-return EmptyStateSEO branch above (this code path runs
  // only when totalEditais > 0).

  // STORY-431 AC12: only emit the Dataset JSON-LD when the period is real
  // (non-empty + has a periodo string). Avoids polluting Google with an
  // "empty Dataset" structured-data entry.
  const shouldEmitJsonLd = periodoNonEmpty && totalEditais > 0;
  const datasetSchema = shouldEmitJsonLd
    ? {
        '@context': 'https://schema.org',
        '@type': 'Dataset',
        name: `Raio-X das Licitações — ${mesDisplay} ${ano}`,
        description: relatorio.periodo,
        url: `https://smartlic.tech/observatorio/${slug}`,
        license: 'https://creativecommons.org/licenses/by/4.0/',
        creator: {
          '@type': 'Organization',
          name: 'SmartLic',
          url: 'https://smartlic.tech',
        },
        temporalCoverage: `${ano}-${String(mes).padStart(2, '0')}`,
        spatialCoverage: 'Brasil',
        distribution: [
          {
            '@type': 'DataDownload',
            encodingFormat: 'text/csv',
            contentUrl: `https://smartlic.tech/v1/observatorio/relatorio/${mes}/${ano}/csv`,
          },
          {
            '@type': 'DataDownload',
            encodingFormat: 'application/json',
            contentUrl: `https://smartlic.tech/v1/observatorio/relatorio/${mes}/${ano}`,
          },
        ],
      }
    : null;

  // Escape `<` to prevent early script-tag termination if backend strings contain `</script>`.
  const toSafeJsonLd = (value: unknown) => JSON.stringify(value).replace(/</g, '\\u003c');

  // Issue #658: BreadcrumbList JSON-LD + visual nav breadcrumb.
  // Pattern: contratos/[setor]/[uf]/page.tsx (JSON-LD) + alertas-publicos/[setor]/[uf]/page.tsx (visual).
  const breadcrumbs = [
    { name: 'Home', url: '/' },
    { name: 'Observatório', url: '/observatorio' },
    { name: `Raio-X — ${mesDisplay} ${ano}`, url: `/observatorio/${slug}` },
  ];

  const breadcrumbSchema = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: breadcrumbs.map((item, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: item.name,
      item: `https://smartlic.tech${item.url}`,
    })),
  };

  return (
    <>
      {datasetSchema && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: toSafeJsonLd(datasetSchema) }}
        />
      )}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: toSafeJsonLd(breadcrumbSchema) }}
      />
      {/* Issue #658: visual breadcrumb (matches alertas-publicos pattern). */}
      <nav aria-label="Breadcrumb" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3 text-sm text-gray-500">
        <ol className="flex flex-wrap items-center gap-1">
          {breadcrumbs.map((item, i) => (
            <li key={item.url + i} className="flex items-center gap-1">
              {i > 0 && <span className="text-gray-400">/</span>}
              {i < breadcrumbs.length - 1 ? (
                <Link href={item.url} className="hover:text-blue-600">{item.name}</Link>
              ) : (
                <span aria-current="page" className="text-gray-900 font-medium">{item.name}</span>
              )}
            </li>
          ))}
        </ol>
      </nav>
      <ObservatorioRelatorioClient
        relatorio={relatorio}
        slug={slug}
        mesDisplay={mesDisplay}
        ano={ano}
        mes={mes}
      />
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <FoundersRibbon
          variant="contextual"
          copy="Receba inteligência B2G sem mensalidade. Acesso vitalício R$997."
          src="pseo_observatorio"
        />
      </div>

      {/* #1519 (NETINT-014): EmbedIntelFeed — compact market intelligence widget */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <EmbedIntelFeed
          sector={(
            relatorio?.setores_em_alta?.[0]?.setor_id
              ? String(relatorio.setores_em_alta[0].setor_id).replace(/_/g, "-")
              : slug
          )}
        />
      </div>
    </>
  );
}
