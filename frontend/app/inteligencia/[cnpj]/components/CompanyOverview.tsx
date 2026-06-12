/**
 * VITRINE-001 (#1612): Company overview component for /inteligencia/[cnpj].
 *
 * Displays company identity data, KPI cards (contract totals, values),
 * and sector classification badge.
 */

'use client';

import type { IntelVitrineData, RankingInfoVitrine } from '../page';

interface Props {
  vitrine: IntelVitrineData;
  formatBRL: (value: number) => string;
  cnpjMasked: string;
}

export default function CompanyOverview({ vitrine, formatBRL, cnpjMasked }: Props) {
  return (
    <section className="mb-10">
      {/* Identity Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-ink tracking-tight mb-2">
            {vitrine.razao_social}
          </h1>
          {vitrine.nome_fantasia && (
            <p className="text-sm text-ink-secondary mb-1">{vitrine.nome_fantasia}</p>
          )}
          <p className="text-xs text-ink-secondary">
            CNPJ: {cnpjMasked}
            {vitrine.setor_nome && <> &middot; {vitrine.setor_nome}</>}
          </p>
        </div>

        {vitrine.setor_nome && (
          <span className="inline-flex items-center rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800 shrink-0">
            {vitrine.setor_nome}
          </span>
        )}
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="bg-surface-1 border border-[var(--border)] rounded-xl p-4">
          <p className="text-xs text-ink-secondary mb-1">Contratos (12 meses)</p>
          <p className="text-xl sm:text-2xl font-bold text-ink">
            {vitrine.total_contratos_12m.toLocaleString('pt-BR')}
          </p>
        </div>
        <div className="bg-surface-1 border border-[var(--border)] rounded-xl p-4">
          <p className="text-xs text-ink-secondary mb-1">Valor (12 meses)</p>
          <p className="text-xl sm:text-2xl font-bold text-green-700">
            {formatBRL(vitrine.valor_total_12m)}
          </p>
        </div>
        <div className="bg-surface-1 border border-[var(--border)] rounded-xl p-4">
          <p className="text-xs text-ink-secondary mb-1">Total Contratos</p>
          <p className="text-xl sm:text-2xl font-bold text-ink">
            {vitrine.total_contratos_alltime.toLocaleString('pt-BR')}
          </p>
        </div>
        <div className="bg-surface-1 border border-[var(--border)] rounded-xl p-4">
          <p className="text-xs text-ink-secondary mb-1">Valor Total</p>
          <p className="text-xl sm:text-2xl font-bold text-green-700">
            {formatBRL(vitrine.valor_total_alltime)}
          </p>
        </div>
      </div>
    </section>
  );
}
