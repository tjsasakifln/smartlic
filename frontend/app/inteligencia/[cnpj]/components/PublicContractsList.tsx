/**
 * VITRINE-001 (#1612): PublicContractsList component.
 *
 * Displays the top public buyer organizations for the company.
 */
import Link from 'next/link';
import type { IntelVitrineData } from '../page';

interface Props {
  vitrine: IntelVitrineData;
  formatBRL: (value: number) => string;
}

export function PublicContractsList({ vitrine, formatBRL }: Props) {
  if (vitrine.top_orgaos.length === 0) return null;

  return (
    <section className="mb-10">
      <h2 className="text-xl font-semibold text-ink mb-4">
        Principais Órgãos Compradores
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {vitrine.top_orgaos.map((orgao) => (
          <Link
            key={orgao.cnpj}
            href={`/orgaos/${orgao.cnpj}`}
            className="block bg-surface-1 border border-[var(--border)] rounded-xl p-4 hover:shadow-md transition-shadow"
          >
            <p className="text-sm font-semibold text-ink mb-2 line-clamp-2">
              {orgao.nome}
            </p>
            <div className="flex justify-between text-xs text-ink-secondary">
              <span>{orgao.total_contratos} contratos</span>
              <span className="text-green-700 font-medium">
                {formatBRL(orgao.valor_total)}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
