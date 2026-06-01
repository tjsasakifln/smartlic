/**
 * TopBuyersBlock — Top organs/buyers or fornecedores list for use-case pages
 *
 * RSC that renders a ranked table of top buyers or top suppliers.
 * Used by /para-empresas-de-ti, /para-construtoras, /para-quem-quer-subcontratar.
 */
export interface TopItem {
  name: string;
  count: number;
  value?: number;
}

interface TopBuyersBlockProps {
  title: string;
  subtitle: string;
  items: TopItem[];
  /** Label for the "Quantidade" column */
  countLabel?: string;
  /** Label for the "Valor" column */
  valueLabel?: string;
  /** Whether to show index ranking */
  showRanking?: boolean;
  /** When data is unavailable */
  unavailable?: boolean;
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(value);
}

export default function TopBuyersBlock({
  title,
  subtitle,
  items,
  countLabel = 'Contratos',
  valueLabel = 'Valor total',
  showRanking = true,
  unavailable = false,
}: TopBuyersBlockProps) {
  return (
    <section className="py-16">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
        <h2 className="text-3xl sm:text-4xl font-bold text-ink text-center mb-4">
          {title}
        </h2>
        <p className="text-lg text-ink-secondary text-center max-w-2xl mx-auto mb-12">
          {subtitle}
        </p>

        {unavailable || items.length === 0 ? (
          <div className="text-center py-12 bg-surface-1 rounded-xl border border-[color:var(--border)]">
            <p className="text-ink-secondary">Dados sendo carregados das fontes oficiais.</p>
            <p className="text-sm text-ink-muted mt-1">Atualizamos os dados a cada 6 horas.</p>
          </div>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-[color:var(--border)]">
            <table className="w-full text-left">
              <thead>
                <tr className="bg-surface-1 border-b border-[color:var(--border)]">
                  {showRanking && (
                    <th className="px-4 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider w-10">
                      #
                    </th>
                  )}
                  <th className="px-4 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider">
                    Nome
                  </th>
                  <th className="px-4 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider text-right">
                    {countLabel}
                  </th>
                  {items[0]?.value !== undefined && (
                    <th className="px-4 py-3 text-xs font-semibold text-ink-muted uppercase tracking-wider text-right">
                      {valueLabel}
                    </th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-[color:var(--border)]">
                {items.slice(0, 10).map((item, i) => (
                  <tr key={i} className="bg-surface-0 hover:bg-surface-1 transition-colors">
                    {showRanking && (
                      <td className="px-4 py-3 text-sm text-ink-muted font-medium">
                        {i + 1}
                      </td>
                    )}
                    <td className="px-4 py-3 text-sm font-medium text-ink">
                      {item.name}
                    </td>
                    <td className="px-4 py-3 text-sm text-ink-secondary text-right tabular-nums">
                      {item.count.toLocaleString('pt-BR')}
                    </td>
                    {item.value !== undefined && (
                      <td className="px-4 py-3 text-sm text-ink-secondary text-right tabular-nums">
                        {formatCurrency(item.value)}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
