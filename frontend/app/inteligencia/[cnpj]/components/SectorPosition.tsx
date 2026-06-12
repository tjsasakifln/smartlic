/**
 * VITRINE-001 (#1612): SectorPosition component.
 *
 * Displays the sector ranking card showing percentile position,
 * contextual text, and comparison with other companies.
 */
import type { IntelVitrineData } from '../page';

interface Props {
  vitrine: IntelVitrineData;
}

export function SectorPosition({ vitrine }: Props) {
  if (!vitrine.ranking) return null;

  return (
    <section className="mb-10 rounded-xl border border-amber-200 bg-amber-50 p-6">
      <div className="flex items-start gap-4">
        <div className="shrink-0 w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center">
          <span className="text-2xl">&#x1F3C6;</span>
        </div>
        <div>
          <h2 className="text-lg font-bold text-amber-900 mb-1">
            Ranking Setorial
          </h2>
          <p className="text-base text-amber-800">
            {vitrine.ranking.texto_contexto}
          </p>
          <p className="text-xs text-amber-600 mt-2">
            Comparativo com {vitrine.ranking.total_empresas_setor.toLocaleString('pt-BR')} empresas do mesmo setor
          </p>
        </div>
      </div>
    </section>
  );
}
