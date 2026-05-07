'use client';

import { useState, useCallback } from 'react';
import { SITE_URL } from '@/lib/seo';

interface PublicStat {
  id: string;
  label: string;
  value: number;
  formatted_value: string;
  unit: string;
  context: string;
  source: string;
  period: string;
  sector?: string | null;
  uf?: string | null;
}

interface EstatisticasClientProps {
  stats: PublicStat[];
  updatedAt: string;
  freshnessLabel: string;
}

function formatBRL(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(value);
}

function buildCitationHtml(stat: PublicStat, dateStr: string): string {
  return `<blockquote cite="${SITE_URL}/estatisticas">
  ${stat.formatted_value} ${stat.label} — SmartLic, dados oficiais processados, ${dateStr}.
  <a href="${SITE_URL}/estatisticas">Fonte: SmartLic</a>
</blockquote>`;
}

function buildCitationAcademic(stat: PublicStat, todayStr: string): string {
  return `SmartLic. "${stat.label}": ${stat.formatted_value}. Dados das fontes oficiais processados pelo SmartLic. Disponível em: ${SITE_URL}/estatisticas. Acesso em: ${todayStr}.`;
}

function StatCard({ stat }: { stat: PublicStat }) {
  const [copiedHtml, setCopiedHtml] = useState(false);
  const [copiedAcademic, setCopiedAcademic] = useState(false);

  const today = new Date();
  const dateStr = today.toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' });
  const todayStr = today.toLocaleDateString('pt-BR');

  const handleCopyHtml = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(buildCitationHtml(stat, dateStr));
      setCopiedHtml(true);
      setTimeout(() => setCopiedHtml(false), 2500);
    } catch {
      // clipboard not available in some environments
    }
  }, [stat, dateStr]);

  const handleCopyAcademic = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(buildCitationAcademic(stat, todayStr));
      setCopiedAcademic(true);
      setTimeout(() => setCopiedAcademic(false), 2500);
    } catch {
      // clipboard not available
    }
  }, [stat, todayStr]);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 flex flex-col gap-3 shadow-sm hover:shadow-md transition-shadow">
      {/* Period badge */}
      <span className="inline-block text-xs font-medium text-indigo-600 bg-indigo-50 rounded-full px-2.5 py-0.5 w-fit">
        {stat.period}
      </span>

      {/* Label */}
      <p className="text-sm text-gray-600 leading-snug">{stat.label}</p>

      {/* Value */}
      <p className="text-3xl font-bold text-gray-900 leading-none tracking-tight">
        {stat.formatted_value}
        {stat.unit && stat.unit !== 'R$' && stat.unit !== '%' && (
          <span className="text-base font-normal text-gray-500 ml-1">{stat.unit}</span>
        )}
      </p>

      {/* Context */}
      <p className="text-xs text-gray-500 leading-relaxed">{stat.context}</p>

      {/* Tags */}
      <div className="flex flex-wrap gap-1.5">
        {stat.uf && (
          <span className="text-xs bg-blue-50 text-blue-700 rounded px-2 py-0.5 font-medium">
            {stat.uf}
          </span>
        )}
        {stat.sector && (
          <span className="text-xs bg-green-50 text-green-700 rounded px-2 py-0.5 font-medium truncate max-w-[160px]">
            {stat.sector}
          </span>
        )}
      </div>

      {/* Source */}
      <p className="text-[11px] text-gray-400 mt-auto">{stat.source}</p>

      {/* Citation buttons */}
      <div className="flex gap-2 pt-1 border-t border-gray-100">
        <button
          onClick={handleCopyHtml}
          className="flex-1 text-xs py-1.5 px-2 rounded bg-gray-50 hover:bg-gray-100 text-gray-600 hover:text-gray-900 transition-colors text-center"
          title="Copia o snippet HTML com blockquote e backlink"
        >
          {copiedHtml ? 'Copiado!' : 'Citar esta estatística'}
        </button>
        <button
          onClick={handleCopyAcademic}
          className="flex-1 text-xs py-1.5 px-2 rounded bg-gray-50 hover:bg-gray-100 text-gray-600 hover:text-gray-900 transition-colors text-center"
          title="Copia citação no formato acadêmico ABNT"
        >
          {copiedAcademic ? 'Copiado!' : 'Copiar citação'}
        </button>
      </div>
    </div>
  );
}

export default function EstatisticasClient({
  stats,
  updatedAt,
  freshnessLabel,
}: EstatisticasClientProps) {
  return (
    <div>
      {/* Freshness indicator */}
      <p className="text-sm text-gray-500 mb-6">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
          {freshnessLabel}
          {' · '}
          <time dateTime={updatedAt} className="tabular-nums">
            {new Date(updatedAt).toLocaleString('pt-BR', {
              day: '2-digit',
              month: '2-digit',
              year: 'numeric',
              hour: '2-digit',
              minute: '2-digit',
            })}
          </time>
        </span>
      </p>

      {/* Stats grid */}
      {stats.length === 0 ? (
        <p className="text-gray-500 py-8 text-center">
          Dados sendo carregados. Tente novamente em alguns instantes.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {stats.map((stat) => (
            <StatCard key={stat.id} stat={stat} />
          ))}
        </div>
      )}
    </div>
  );
}
