/**
 * SEO-P2-010 (#995): Tests for <RelatedArticles /> + relatedResolver.
 *
 * Covers:
 * - Resolver: deterministic shuffle, currentUrl exclusion, dedup, 4-8 cap.
 * - Resolver: per-context-type wiring (sector/cluster/glossary/question/cnpj).
 * - Component: renders semantic <aside> + ItemList JSON-LD + descriptive
 *   anchor text.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import RelatedArticles from '../components/seo/RelatedArticles';
import {
  resolveRelated,
  deterministicShuffle,
  type RelatedLink,
} from '../lib/seo/relatedResolver';

// ---------------------------------------------------------------------------
// Resolver
// ---------------------------------------------------------------------------

describe('relatedResolver / resolveRelated', () => {
  it('returns 4-8 links for a known sector', () => {
    const links = resolveRelated({
      type: 'sector',
      value: 'informatica',
      currentUrl: '/blog/programmatic/informatica',
    });
    expect(links.length).toBeGreaterThanOrEqual(4);
    expect(links.length).toBeLessThanOrEqual(8);
  });

  it('clamps explicit limit to [4, 8]', () => {
    const tooFew = resolveRelated(
      {
        type: 'sector',
        value: 'informatica',
        currentUrl: '/blog/programmatic/informatica',
      },
      { limit: 1 },
    );
    const tooMany = resolveRelated(
      {
        type: 'sector',
        value: 'informatica',
        currentUrl: '/blog/programmatic/informatica',
      },
      { limit: 50 },
    );
    expect(tooFew.length).toBeGreaterThanOrEqual(4);
    expect(tooMany.length).toBeLessThanOrEqual(8);
  });

  it('never returns the currentUrl in the result set', () => {
    const currentUrl = '/blog/programmatic/informatica';
    const links = resolveRelated({
      type: 'sector',
      value: 'informatica',
      currentUrl,
    });
    expect(links.find((l) => l.href === currentUrl)).toBeUndefined();
  });

  it('produces deterministic order for the same currentUrl', () => {
    const ctx = {
      type: 'sector' as const,
      value: 'informatica',
      currentUrl: '/blog/programmatic/informatica',
    };
    const a = resolveRelated(ctx);
    const b = resolveRelated(ctx);
    expect(a.map((l) => l.href)).toEqual(b.map((l) => l.href));
  });

  it('produces different order for different currentUrl (anti-doorway)', () => {
    const a = resolveRelated({
      type: 'sector',
      value: 'informatica',
      currentUrl: '/blog/programmatic/informatica',
    });
    const b = resolveRelated({
      type: 'sector',
      value: 'informatica',
      currentUrl: '/blog/contratos/informatica',
    });
    // The two pools are the same; but order must diverge so that crawlers
    // don't see the exact same ItemList everywhere.
    const orderA = a.map((l) => l.href).join('|');
    const orderB = b.map((l) => l.href).join('|');
    expect(orderA).not.toEqual(orderB);
  });

  it('de-duplicates by href', () => {
    const links = resolveRelated({
      type: 'sector',
      value: 'informatica',
      currentUrl: '/blog/programmatic/informatica',
    });
    const hrefs = links.map((l) => l.href);
    expect(new Set(hrefs).size).toEqual(hrefs.length);
  });

  it('returns links for glossary context', () => {
    const links = resolveRelated({
      type: 'glossary',
      value: 'pregao-eletronico',
      currentUrl: '/glossario/pregao-eletronico',
    });
    // Even if the term has no related entries, resolver returns [] not throw.
    expect(Array.isArray(links)).toBe(true);
  });

  it('returns links for question context with sibling questions', () => {
    // Pull the first available question slug from the registry to make
    // the test resilient to content shuffles.
    const { QUESTIONS } = require('../lib/questions');
    if (QUESTIONS.length === 0) return;
    const sample = QUESTIONS[0];
    const links = resolveRelated({
      type: 'question',
      value: sample.slug,
      currentUrl: `/perguntas/${sample.slug}`,
    });
    expect(Array.isArray(links)).toBe(true);
    // Self-link must be absent.
    expect(links.find((l) => l.href === `/perguntas/${sample.slug}`)).toBeUndefined();
  });

  it('returns evergreen tools for cnpj context', () => {
    const links = resolveRelated({
      type: 'cnpj',
      value: '12345678000190',
      currentUrl: '/cnpj/12345678000190',
    });
    expect(links.length).toBeGreaterThanOrEqual(4);
    const hrefs = links.map((l) => l.href);
    expect(hrefs).toEqual(expect.arrayContaining(['/calculadora']));
  });

  it('returns [] for unknown context safely', () => {
    const links = resolveRelated({
      // @ts-expect-error — intentionally invalid for safety check
      type: 'nope',
      value: 'x',
      currentUrl: '/x',
    });
    expect(links).toEqual([]);
  });
});

describe('relatedResolver / deterministicShuffle', () => {
  it('is stable for the same seed', () => {
    const items = ['a', 'b', 'c', 'd', 'e'];
    expect(deterministicShuffle(items, 'seed1')).toEqual(
      deterministicShuffle(items, 'seed1'),
    );
  });

  it('preserves the input multiset', () => {
    const items = ['a', 'b', 'c', 'd', 'e'];
    const shuffled = deterministicShuffle(items, 'seed1');
    expect([...shuffled].sort()).toEqual([...items].sort());
  });
});

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

const SAMPLE_LINKS: RelatedLink[] = [
  {
    title: 'Como aumentar taxa de vitória em pregões',
    description: 'Guia prático para empresas B2G.',
    href: '/blog/como-aumentar-taxa-vitoria-licitacoes',
    kind: 'artigo',
  },
  {
    title: 'O que é Pregão Eletrônico',
    href: '/glossario/pregao-eletronico',
    kind: 'glossario',
  },
  {
    title: 'Como funciona a habilitação?',
    description: 'Documentos exigidos no SICAF.',
    href: '/perguntas/como-funciona-habilitacao',
    kind: 'pergunta',
  },
  {
    title: 'Calculadora de Oportunidades',
    href: '/calculadora',
    kind: 'ferramenta',
  },
];

describe('<RelatedArticles />', () => {
  it('renders an <aside> with semantic heading', () => {
    render(
      <RelatedArticles
        context={{
          type: 'glossary',
          value: 'edital',
          currentUrl: '/glossario/edital',
        }}
        links={SAMPLE_LINKS}
      />,
    );
    const aside = screen.getByRole('complementary');
    expect(aside).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: /continue explorando/i }),
    ).toBeInTheDocument();
  });

  it('renders all provided links with descriptive anchor text', () => {
    render(
      <RelatedArticles
        context={{
          type: 'glossary',
          value: 'edital',
          currentUrl: '/glossario/edital',
        }}
        links={SAMPLE_LINKS}
      />,
    );
    for (const link of SAMPLE_LINKS) {
      const a = screen.getByRole('link', { name: new RegExp(link.title, 'i') });
      expect(a).toHaveAttribute('href', link.href);
    }
  });

  it('uses non-generic anchor text (no "leia mais" / "veja também")', () => {
    render(
      <RelatedArticles
        context={{
          type: 'glossary',
          value: 'edital',
          currentUrl: '/glossario/edital',
        }}
        links={SAMPLE_LINKS}
      />,
    );
    expect(screen.queryByText(/leia mais/i)).toBeNull();
    expect(screen.queryByText(/veja também/i)).toBeNull();
  });

  it('emits schema.org ItemList JSON-LD with item count', () => {
    const { container } = render(
      <RelatedArticles
        context={{
          type: 'glossary',
          value: 'edital',
          currentUrl: '/glossario/edital',
        }}
        links={SAMPLE_LINKS}
      />,
    );
    const ld = container.querySelector('script[type="application/ld+json"]');
    expect(ld).not.toBeNull();
    const parsed = JSON.parse(ld!.textContent ?? '{}');
    expect(parsed['@type']).toBe('ItemList');
    expect(parsed.numberOfItems).toBe(SAMPLE_LINKS.length);
    expect(parsed.itemListElement).toHaveLength(SAMPLE_LINKS.length);
    expect(parsed.itemListElement[0].position).toBe(1);
    expect(parsed.itemListElement[0].url).toMatch(/^https:\/\/smartlic\.tech/);
  });

  it('renders nothing when there are zero links', () => {
    const { container } = render(
      <RelatedArticles
        context={{
          type: 'glossary',
          value: 'edital',
          currentUrl: '/glossario/edital',
        }}
        links={[]}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it('honours a custom heading', () => {
    render(
      <RelatedArticles
        context={{
          type: 'sector',
          value: 'informatica',
          currentUrl: '/blog/programmatic/informatica',
        }}
        links={SAMPLE_LINKS}
        heading="Saiba mais sobre licitações"
      />,
    );
    expect(
      screen.getByRole('heading', { name: /saiba mais sobre licitações/i }),
    ).toBeInTheDocument();
  });
});
