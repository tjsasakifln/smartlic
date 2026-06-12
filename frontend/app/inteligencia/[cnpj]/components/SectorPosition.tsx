/**
 * VITRINE-001 (#1612): Sector position component for /inteligencia/[cnpj].
 *
 * Displays the company's percentile ranking within its sector,
 * using the backend-computed ranking info with contextual message.
 */

'use client';

import type { RankingInfoVitrine } from '../page';

interface Props {
  ranking: RankingInfoVitrine | null;
}

export default function SectorPosition({ ranking }: Props) {
  if (!ranking) return null;

  return (
    <section className="mb-10 rounded-xl border border-amber-200 bg-amber-50 p-6">
      <div className="flex items-start gap-4">
        <div className="shrink-0 w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
          <span className="text-2xl" role="img" aria-label="Trophy">
            &#x1F3C6;
          </span>
        </div>
        <div>
          <h2 className="text-lg font-bold text-amber-900 mb-1">
            Ranking Setorial
          </h2>
          <p className="text-base text-amber-800">{ranking.texto_contexto}</p>
          <p className="text-xs text-amber-600 mt-2">
            Comparativo com{' '}
            {ranking.total_empresas_setor.toLocaleString('pt-BR')} empresas do
            mesmo setor
          </p>
        </div>
      </div>
    </section>
  );
}
