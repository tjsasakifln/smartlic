import { Metadata } from 'next';
import Link from 'next/link';
import LandingNavbar from '../components/landing/LandingNavbar';
import Footer from '../components/Footer';
import { GLOSSARY_TERMS, type GlossaryTerm } from '@/lib/glossary-terms';
import { buildCanonical } from '@/lib/seo';

export const metadata: Metadata = {
  title: 'Glossário de Licitações: 50 Termos Essenciais',
  description:
    'Glossário completo com 50 termos de licitações públicas explicados de forma prática. Adjudicação, pregão eletrônico, PNCP, SRP e mais. Referência essencial para empresas B2G.',
  alternates: {
    canonical: buildCanonical('/glossario'),
  },
  openGraph: {
    title: 'Glossário de Licitações: 50 Termos Essenciais | SmartLic',
    description:
      'Referência completa para profissionais de licitações. 50 termos explicados com definições claras e exemplos práticos.',
    type: 'website',
    url: buildCanonical('/glossario'),
    siteName: 'SmartLic',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Glossário de Licitações: 50 Termos Essenciais | SmartLic',
    description:
      'Referência completa para profissionais de licitações. 50 termos explicados com definições claras e exemplos práticos.',
  },
};

/* ---------------------------------------------------------------------------
 * Data — shared module (also used by /glossario/[termo])
 * --------------------------------------------------------------------------- */

const TERMS: GlossaryTerm[] = GLOSSARY_TERMS;

/* ---------------------------------------------------------------------------
 * Helpers
 * --------------------------------------------------------------------------- */

/** Extract unique first letters (uppercase) from sorted terms. */
function getAlphabetLetters(terms: GlossaryTerm[]): string[] {
  const set = new Set<string>();
  for (const t of terms) {
    set.add(t.term.charAt(0).toUpperCase());
  }
  return Array.from(set).sort();
}

/** Group terms by their first letter. */
function groupByLetter(terms: GlossaryTerm[]): Record<string, GlossaryTerm[]> {
  const groups: Record<string, GlossaryTerm[]> = {};
  for (const t of terms) {
    const letter = t.term.charAt(0).toUpperCase();
    if (!groups[letter]) groups[letter] = [];
    groups[letter].push(t);
  }
  return groups;
}

/* ---------------------------------------------------------------------------
 * Component
 * --------------------------------------------------------------------------- */

export default function GlossárioPage() {
  const letters = getAlphabetLetters(TERMS);
  const grouped = groupByLetter(TERMS);

  /* JSON-LD: BreadcrumbList */
  const breadcrumbLd = {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: [
      {
        '@type': 'ListItem',
        position: 1,
        name: 'Home',
        item: buildCanonical('/'),
      },
      {
        '@type': 'ListItem',
        position: 2,
        name: 'Glossário',
        item: buildCanonical('/glossario'),
      },
    ],
  };

  /* JSON-LD: DefinedTerm array */
  const definedTermsLd = TERMS.map((t) => ({
    '@type': 'DefinedTerm',
    name: t.term,
    description: t.definition,
    inDefinedTermSet: {
      '@type': 'DefinedTermSet',
      name: 'Glossário de Licitações SmartLic',
    },
  }));

  const definedTermSetLd = {
    '@context': 'https://schema.org',
    '@type': 'DefinedTermSet',
    name: 'Glossário de Licitações SmartLic',
    description:
      'Glossário com 50 termos essenciais sobre licitações públicas no Brasil.',
    url: buildCanonical('/glossario'),
    hasDefinedTerm: definedTermsLd,
  };

  return (
    <div className="min-h-screen flex flex-col bg-canvas">
      <LandingNavbar />

      {/* JSON-LD */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbLd) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(definedTermSetLd) }}
      />

      <main className="flex-1">
        {/* ── Hero ── */}
        <div className="bg-surface-1 border-b border-[var(--border)]">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 lg:py-20 text-center">
            <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold text-ink tracking-tight mb-4">
              Glossário de Licitações
            </h1>
            <p className="text-base sm:text-lg text-ink-secondary max-w-2xl mx-auto leading-relaxed">
              50 termos essenciais explicados de forma prática para quem participa de licitações públicas no Brasil
            </p>
          </div>
        </div>

        {/* ── Alphabetical Navigation ── */}
        <div className="sticky top-0 z-20 bg-canvas/95 backdrop-blur-sm border-b border-[var(--border)]">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <nav
              aria-label="Navegacao alfabetica"
              className="flex flex-wrap gap-1 py-3 justify-center"
            >
              {letters.map((letter) => (
                <a
                  key={letter}
                  href={`#letra-${letter}`}
                  className="inline-flex items-center justify-center w-9 h-9 rounded-md text-sm font-semibold text-ink-secondary hover:text-brand-blue hover:bg-surface-1 transition-colors"
                >
                  {letter}
                </a>
              ))}
            </nav>
          </div>
        </div>

        {/* ── Terms ── */}
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
          {letters.map((letter) => (
            <section key={letter} id={`letra-${letter}`} className="mb-12">
              <h2 className="text-2xl font-bold text-brand-blue border-b-2 border-brand-blue/20 pb-2 mb-6">
                {letter}
              </h2>

              <div className="space-y-8">
                {grouped[letter].map((t) => (
                  <article
                    key={t.slug}
                    id={t.slug}
                    className="scroll-mt-24"
                  >
                    <h3 className="text-lg font-bold text-ink mb-1">
                      <Link
                        href={`/glossario/${t.slug}`}
                        className="hover:text-brand-blue transition-colors"
                      >
                        {t.term}
                      </Link>
                    </h3>
                    <p className="text-ink-secondary leading-relaxed mb-3">
                      {t.definition}
                    </p>

                    {/* Example box */}
                    <div className="text-sm bg-surface-1 border border-[var(--border)] rounded-lg p-3 mb-2">
                      <span className="font-semibold text-ink">Exemplo: </span>
                      <span className="text-ink-secondary">{t.example}</span>
                    </div>

                    <Link
                      href={t.guideHref}
                      className="text-brand-blue hover:underline text-sm"
                    >
                      {t.guideLabel} &rarr;
                    </Link>
                  </article>
                ))}
              </div>
            </section>
          ))}

          {/* ── CTA ── */}
          <section className="mt-16 mb-8 rounded-2xl bg-brand-blue p-8 sm:p-10 text-center">
            <h2 className="text-2xl sm:text-3xl font-bold text-white mb-3">
              Encontre licitações do seu setor automaticamente
            </h2>
            <p className="text-white/85 max-w-xl mx-auto mb-6">
              O SmartLic monitora as fontes oficiais de licitações diariamente, classifica por setor com IA e avalia viabilidade para voce focar nas melhores oportunidades.
            </p>
            <Link
              href="/signup?source=glossario-cta"
              className="inline-flex items-center gap-2 bg-white text-brand-blue px-8 py-4 rounded-lg font-semibold hover:bg-white/90 transition-colors focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-brand-blue"
            >
              Testar gratis por 14 dias
            </Link>
          </section>
        </div>
      </main>

      <Footer />
    </div>
  );
}
