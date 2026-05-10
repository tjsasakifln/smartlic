import Link from 'next/link';
import {
  resolveRelated,
  type RelatedContext,
  type RelatedLink,
} from '@/lib/seo/relatedResolver';

/**
 * SEO-P2-010 (#995): <RelatedArticles /> — semantic cross-link aside.
 *
 * Server component. Receives a content context and renders 4-8 descriptive
 * internal links derived from the content graph (sector ↔ cluster ↔
 * glossário ↔ perguntas). Markup is `<aside>` + schema.org ItemList for
 * crawlers.
 *
 * Anchor text is always the full title — never "leia mais" or "veja
 * também" — so internal links carry topical signal.
 */
interface RelatedArticlesProps {
  context: RelatedContext;
  /** Override the heading. Defaults to "Continue explorando". */
  heading?: string;
  /** Max links to render (clamped to 4-8). */
  limit?: number;
  /** Extra Tailwind classes for the wrapper. */
  className?: string;
  /** Optional pre-resolved links — useful for tests/snapshots. */
  links?: RelatedLink[];
}

const KIND_LABEL: Record<RelatedLink['kind'], string> = {
  artigo: 'Artigo',
  pergunta: 'Pergunta',
  glossario: 'Glossário',
  setor: 'Setor',
  panorama: 'Panorama',
  ferramenta: 'Ferramenta',
};

export default function RelatedArticles({
  context,
  heading = 'Continue explorando',
  limit,
  className,
  links: linksOverride,
}: RelatedArticlesProps) {
  const links = linksOverride ?? resolveRelated(context, { limit });
  if (links.length === 0) return null;

  // schema.org ItemList structured data — helps crawlers understand the
  // link cluster as a coherent recommendation set.
  const itemListLd = {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: heading,
    itemListOrder: 'https://schema.org/ItemListOrderAscending',
    numberOfItems: links.length,
    itemListElement: links.map((link, idx) => ({
      '@type': 'ListItem',
      position: idx + 1,
      url: link.href.startsWith('http')
        ? link.href
        : `https://smartlic.tech${link.href}`,
      name: link.title,
    })),
  };

  return (
    <aside
      aria-labelledby="related-articles-heading"
      className={`mt-12 pt-8 border-t border-[var(--border)] ${className ?? ''}`}
    >
      <script
        type="application/ld+json"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListLd) }}
      />
      <h2
        id="related-articles-heading"
        className="text-lg font-semibold text-ink mb-4"
      >
        {heading}
      </h2>
      <ul className="grid grid-cols-1 sm:grid-cols-2 gap-3 list-none p-0">
        {links.map((link, idx) => (
          <li key={link.href} className="m-0">
            <Link
              href={link.href}
              className="group flex items-start gap-3 p-3 rounded-lg border border-[var(--border)] hover:border-brand-blue/30 hover:bg-surface-1 transition-colors h-full"
              data-position={idx + 1}
              data-kind={link.kind}
            >
              <span className="shrink-0 mt-0.5 text-xs font-medium px-2 py-0.5 rounded bg-brand-blue-subtle/50 text-brand-blue">
                {KIND_LABEL[link.kind]}
              </span>
              <span className="flex-1 min-w-0">
                <span className="block text-sm font-medium text-ink group-hover:text-brand-blue transition-colors line-clamp-2">
                  {link.title}
                </span>
                {link.description && (
                  <span className="block text-xs text-ink-secondary line-clamp-2 mt-1">
                    {link.description}
                  </span>
                )}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </aside>
  );
}
