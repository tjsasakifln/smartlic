/**
 * MarketDataBlock — Real DataLake statistics grid for use-case landing pages
 *
 * RSC that displays market size, contract count, 90-day trends, and top UFs.
 * Renders gracefully when data is unavailable (shows skeleton-friendly placeholders).
 */
export interface MarketStat {
  label: string;
  value: string;
  context: string;
  icon: 'contracts' | 'value' | 'trend' | 'ufs';
}

interface MarketDataBlockProps {
  title: string;
  subtitle: string;
  stats: MarketStat[];
}

function StatIcon({ icon }: { icon: MarketStat['icon'] }) {
  switch (icon) {
    case 'contracts':
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      );
    case 'value':
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
    case 'trend':
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
        </svg>
      );
    case 'ufs':
      return (
        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      );
  }
}

export default function MarketDataBlock({ title, subtitle, stats }: MarketDataBlockProps) {
  return (
    <section className="py-16 bg-surface-1">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 className="text-3xl sm:text-4xl font-bold text-ink text-center mb-4">
          {title}
        </h2>
        <p className="text-lg text-ink-secondary text-center max-w-2xl mx-auto mb-12">
          {subtitle}
        </p>

        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {stats.map((stat, i) => (
            <div
              key={i}
              className="bg-surface-0 border border-[color:var(--border)] rounded-xl p-6 hover:shadow-md transition-shadow"
            >
              <div className="w-10 h-10 bg-brand-blue/10 rounded-lg flex items-center justify-center mb-4">
                <div className="text-brand-blue">
                  <StatIcon icon={stat.icon} />
                </div>
              </div>
              <p className="text-3xl font-bold text-ink mb-1">{stat.value}</p>
              <p className="font-semibold text-sm text-ink mb-1">{stat.label}</p>
              <p className="text-xs text-ink-secondary">{stat.context}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
