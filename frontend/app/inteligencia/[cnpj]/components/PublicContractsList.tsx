/**
 * VITRINE-001 (#1612): Public contracts list for /inteligencia/[cnpj].
 *
 * Shows top buying organizations with contract counts and values.
 */

'use client';

import Link from 'next/link';
import type { OrgaoInfoVitrine } from '../page';

interface Props {
  topOrgaos: OrgaoInfoVitrine[];
  formatBRL: (value: number) => string;
}

export default function PublicContractsList({ topOrgaos, formatBRL }: Props) {
  if (topOrgaos.length === 0) return null;

  return (
    <section className="mb-10">
      <h2 className="text-xl font-semibold text-ink mb-4">
        Principais Orgaos Compradores
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {topOrgaos.map((orgao) => (
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
