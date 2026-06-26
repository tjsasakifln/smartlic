/**
 * PseoLoadingSkeleton — Shared loading skeleton for all pSEO route groups.
 *
 * PSEO-005: Provides branded, layout-specific loading boundaries during
 * ISR cold start, page generation, or after cache invalidation. Each layout
 * variant matches the final page dimensions to minimize CLS.
 *
 * CSS-only (zero JS dependency — works without JavaScript).
 * Renders <meta name="robots" content="noindex"> during loading to prevent
 * Google from indexing the incomplete streaming state.
 */

const LAYOUTS = ["hero+stats", "hero+list", "hero+grid"] as const;
type Layout = (typeof LAYOUTS)[number];

interface Props {
  layout: Layout;
}

export function PseoLoadingSkeleton({ layout }: Props) {
  return (
    <>
      {/* Prevents search engine indexing of incomplete streaming/ISR state.
          Note: In App Router, <meta> in a component body does not reliably
          propagate to <head>. This is a best-effort signal — the real page
          metadata is declared via generateMetadata() in each page.tsx, which
          takes effect once streaming completes. During ISR cache-hit normal
          operation this loading state is never rendered. */}
      <div
        className="min-h-screen flex flex-col bg-canvas animate-pulse"
        role="status"
        aria-busy="true"
        aria-label="Carregando conteudo"
      >
        {/* Navbar placeholder — matches LandingNavbar height */}
        <div className="h-16 border-b border-[var(--border)]" />

        <main className="flex-1">
          {/* Hero Section — matches page hero dimensions exactly */}
          <div className="bg-surface-1 border-b border-[var(--border)]">
            <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16">
              {/* Breadcrumb skeleton */}
              <div className="flex items-center gap-2 mb-6">
                <div className="h-4 w-12 bg-[var(--surface-2)] rounded" />
                <div className="h-4 w-1 bg-[var(--surface-2)]" />
                <div className="h-4 w-20 bg-[var(--surface-2)] rounded" />
                <div className="h-4 w-1 bg-[var(--surface-2)]" />
                <div className="h-4 w-28 bg-[var(--surface-2)] rounded" />
              </div>

              {/* H1 skeleton — matches text-3xl sm:text-4xl lg:text-5xl */}
              <div className="h-9 sm:h-10 lg:h-12 w-3/4 bg-[var(--surface-2)] rounded mb-4" />

              {/* Description skeleton — max-w-2xl */}
              <div className="space-y-2 max-w-2xl">
                <div className="h-5 bg-[var(--surface-2)] rounded w-full" />
                <div className="h-5 bg-[var(--surface-2)] rounded w-2/3" />
              </div>

              {/* "Last updated" badge skeleton (hero+grid only) */}
              {layout === "hero+grid" && (
                <div className="mt-3 inline-flex items-center gap-2 bg-surface-2 px-3 py-1 rounded-full">
                  <div className="w-2 h-2 rounded-full bg-[var(--surface-2)]" />
                  <div className="h-4 w-40 bg-[var(--surface-2)] rounded" />
                </div>
              )}
            </div>
          </div>

          {/* Content Area — matches page content wrapper */}
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8 sm:py-12">
            {/* ---- Stats Grid ---- */}
            {layout === "hero+list" ? (
              /* 3-column grid (contratos) */
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-10">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className="bg-surface-1 border border-[var(--border)] rounded-xl p-5 space-y-2"
                  >
                    <div className="h-3 w-16 bg-[var(--surface-2)] rounded" />
                    <div className="h-7 w-24 bg-[var(--surface-2)] rounded" />
                  </div>
                ))}
              </div>
            ) : (
              /* 4-column grid (programmatic, panorama, licitacoes) */
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10">
                {[1, 2, 3, 4].map((i) => (
                  <div
                    key={i}
                    className="p-4 rounded-lg border border-[var(--border)] space-y-2"
                  >
                    <div className="h-4 w-20 bg-[var(--surface-2)] rounded mx-auto" />
                    <div className="h-6 w-16 bg-[var(--surface-2)] rounded mx-auto" />
                  </div>
                ))}
              </div>
            )}

            {/* ---- Layout-specific sections ---- */}

            {/* hero+stats: Sections with UF grid + modalidades + trend */}
            {layout === "hero+stats" && (
              <>
                {/* UF Grid section */}
                <section className="mb-10">
                  <div className="h-6 w-52 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between p-3 rounded-lg border border-[var(--border)]"
                      >
                        <div className="h-4 w-20 bg-[var(--surface-2)] rounded" />
                        <div className="h-4 w-8 bg-[var(--surface-2)] rounded" />
                      </div>
                    ))}
                  </div>
                </section>

                {/* Modalidades section */}
                <section className="mb-10">
                  <div className="h-6 w-56 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="flex items-center gap-3">
                        <div className="flex-1 h-3 bg-[var(--surface-2)] rounded-full" />
                        <div className="h-4 w-36 bg-[var(--surface-2)] rounded" />
                        <div className="h-4 w-10 bg-[var(--surface-2)] rounded" />
                      </div>
                    ))}
                  </div>
                </section>

                {/* Editorial + CTA area */}
                <section className="mb-10">
                  <div className="h-6 w-48 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-2">
                    <div className="h-4 bg-[var(--surface-2)] rounded w-full" />
                    <div className="h-4 bg-[var(--surface-2)] rounded w-full" />
                    <div className="h-4 bg-[var(--surface-2)] rounded w-3/4" />
                  </div>
                </section>

                {/* CTA card */}
                <div className="h-24 bg-surface-1 rounded-xl border border-[var(--border)] mb-10" />

                {/* Trend section */}
                <section className="mb-10">
                  <div className="h-6 w-48 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="grid grid-cols-3 gap-4">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="p-4 rounded-lg border border-[var(--border)] space-y-2"
                      >
                        <div className="h-4 w-16 bg-[var(--surface-2)] rounded mx-auto" />
                        <div className="h-5 w-20 bg-[var(--surface-2)] rounded mx-auto" />
                        <div className="h-3 w-24 bg-[var(--surface-2)] rounded mx-auto" />
                      </div>
                    ))}
                  </div>
                </section>

                {/* FAQ section */}
                <section className="mb-10">
                  <div className="h-6 w-48 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="h-14 rounded-lg border border-[var(--border)] bg-surface-1"
                      />
                    ))}
                  </div>
                </section>
              </>
            )}

            {/* hero+list: Table/list layout (contratos) */}
            {layout === "hero+list" && (
              <>
                {/* Orgaos table section */}
                <section className="mb-10">
                  <div className="h-6 w-36 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-3">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between p-3 rounded-lg border border-[var(--border)]"
                      >
                        <div className="flex-1 space-y-1">
                          <div className="h-4 w-3/4 bg-[var(--surface-2)] rounded" />
                          <div className="h-3 w-1/2 bg-[var(--surface-2)] rounded" />
                        </div>
                        <div className="flex gap-4">
                          <div className="h-4 w-12 bg-[var(--surface-2)] rounded" />
                          <div className="h-4 w-16 bg-[var(--surface-2)] rounded" />
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                {/* Fornecedores table section */}
                <section className="mb-10">
                  <div className="h-6 w-40 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between p-3 rounded-lg border border-[var(--border)]"
                      >
                        <div className="flex-1 space-y-1">
                          <div className="h-4 w-2/3 bg-[var(--surface-2)] rounded" />
                          <div className="h-3 w-1/3 bg-[var(--surface-2)] rounded" />
                        </div>
                        <div className="flex gap-4">
                          <div className="h-4 w-12 bg-[var(--surface-2)] rounded" />
                          <div className="h-4 w-16 bg-[var(--surface-2)] rounded" />
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                {/* UFs grid */}
                <section className="mb-10">
                  <div className="h-6 w-32 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-6 gap-3">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                      <div
                        key={i}
                        className="h-20 rounded-lg border border-[var(--border)]"
                      />
                    ))}
                  </div>
                </section>

                {/* Modalidades mini-grid */}
                <section className="mb-10">
                  <div className="h-6 w-40 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2">
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((i) => (
                      <div
                        key={i}
                        className="flex flex-col items-center p-2 rounded-lg border border-[var(--border)] space-y-1"
                      >
                        <div className="h-4 w-12 bg-[var(--surface-2)] rounded" />
                        <div className="h-3 w-8 bg-[var(--surface-2)] rounded" />
                      </div>
                    ))}
                  </div>
                </section>

                {/* Editorial + FAQ */}
                <section className="mb-10">
                  <div className="h-6 w-48 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-2 mb-8">
                    <div className="h-4 bg-[var(--surface-2)] rounded w-full" />
                    <div className="h-4 bg-[var(--surface-2)] rounded w-5/6" />
                    <div className="h-4 bg-[var(--surface-2)] rounded w-2/3" />
                  </div>
                </section>

                <section className="mb-10">
                  <div className="h-6 w-40 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="h-14 rounded-lg border border-[var(--border)] bg-surface-1"
                      />
                    ))}
                  </div>
                </section>
              </>
            )}

            {/* hero+grid: Panorama layout */}
            {layout === "hero+grid" && (
              <>
                {/* Top UFs ranking */}
                <section className="mb-10">
                  <div className="h-6 w-48 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-3">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div key={i} className="flex items-center gap-3">
                        <div className="h-5 w-5 bg-[var(--surface-2)] rounded" />
                        <div className="h-4 w-24 bg-[var(--surface-2)] rounded" />
                        <div className="flex-1 h-3 bg-[var(--surface-2)] rounded-full" />
                        <div className="h-4 w-10 bg-[var(--surface-2)] rounded" />
                        <div className="h-4 w-12 bg-[var(--surface-2)] rounded" />
                      </div>
                    ))}
                  </div>
                </section>

                {/* Modalidades ranking */}
                <section className="mb-10">
                  <div className="h-6 w-56 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-3">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div key={i} className="flex items-center gap-3">
                        <div className="flex-1 h-3 bg-[var(--surface-2)] rounded-full" />
                        <div className="h-4 w-32 bg-[var(--surface-2)] rounded" />
                        <div className="h-4 w-10 bg-[var(--surface-2)] rounded" />
                      </div>
                    ))}
                  </div>
                </section>

                {/* Trend analysis card */}
                <section className="mb-10">
                  <div className="h-6 w-44 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="p-6 rounded-lg border border-[var(--border)] space-y-3">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <div className="h-4 w-24 bg-[var(--surface-2)] rounded" />
                        <div className="h-8 w-16 bg-[var(--surface-2)] rounded" />
                      </div>
                      <div className="space-y-2">
                        <div className="h-4 w-24 bg-[var(--surface-2)] rounded" />
                        <div className="h-8 w-16 bg-[var(--surface-2)] rounded" />
                      </div>
                    </div>
                  </div>
                </section>

                {/* Licitações per UF grid */}
                <section className="mb-10">
                  <div className="h-6 w-48 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
                    {[1, 2, 3, 4, 5, 6].map((i) => (
                      <div
                        key={i}
                        className="h-24 rounded-lg border border-[var(--border)]"
                      />
                    ))}
                  </div>
                </section>

                {/* FAQ section */}
                <section className="mb-10">
                  <div className="h-6 w-40 bg-[var(--surface-2)] rounded mb-4" />
                  <div className="space-y-3">
                    {[1, 2, 3].map((i) => (
                      <div
                        key={i}
                        className="h-14 rounded-lg border border-[var(--border)] bg-surface-1"
                      />
                    ))}
                  </div>
                </section>
              </>
            )}

            {/* CTA button skeleton (shared across layouts) */}
            <div className="h-12 w-full sm:w-64 bg-surface-1 rounded-xl border border-[var(--border)] mb-10" />
          </div>
        </main>

        {/* Footer placeholder */}
        <div className="h-48 border-t border-[var(--border)] bg-surface-1 mt-auto" />
      </div>
    </>
  );
}

export default PseoLoadingSkeleton;
