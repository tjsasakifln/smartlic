import { useState } from "react";
import { UF_NAMES, UFS } from "../../../lib/constants/uf-names";
import { Label } from "../../../components/ui/Label";
import { ValueRangeSelector } from "./ValueRangeSelector";
import { REGIONS, type OnboardingData } from "./types";

interface OnboardingStep2Props {
  data: OnboardingData;
  onChange: (partial: Partial<OnboardingData>) => void;
  errors: Record<string, { message?: string }>;
}

export function OnboardingStep2({ data, onChange, errors }: OnboardingStep2Props) {
  // COPY-COP-005: On mobile, collapse value range to show only 4 required fields
  const [showValueRange, setShowValueRange] = useState(false);
  const toggleUf = (uf: string) => {
    const current = new Set(data.ufs_atuacao);
    if (current.has(uf)) current.delete(uf);
    else current.add(uf);
    onChange({ ufs_atuacao: Array.from(current) });
  };

  const toggleRegion = (regionUfs: string[]) => {
    const current = new Set(data.ufs_atuacao);
    const allSelected = regionUfs.every((uf) => current.has(uf));
    if (allSelected) regionUfs.forEach((uf) => current.delete(uf));
    else regionUfs.forEach((uf) => current.add(uf));
    onChange({ ufs_atuacao: Array.from(current) });
  };

  const selectAll = () => onChange({ ufs_atuacao: [...UFS] });
  const clearAll = () => onChange({ ufs_atuacao: [] });

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold text-[var(--ink)] mb-1">Onde você atua e qual valor ideal?</h2>
        <p className="text-sm text-[var(--ink-secondary)]">
          Selecione estados e faixa de valor para encontrar oportunidades compatíveis
        </p>
      </div>

      {/* UFs de atuação */}
      <div
        role="group"
        aria-labelledby="ufs-label"
        aria-invalid={!!errors.ufs_atuacao}
        aria-describedby={errors.ufs_atuacao ? "ufs-error" : undefined}
      >
        <div className="flex items-center justify-between mb-2">
          <Label required id="ufs-label">Estados de atuação <span className="font-normal text-ink-secondary">({data.ufs_atuacao.length} selecionados)</span></Label>
          <div className="flex gap-2">
            <button onClick={selectAll} className="text-xs text-[var(--brand-blue)] hover:underline">
              Todos
            </button>
            <button onClick={clearAll} className="text-xs text-[var(--ink-secondary)] hover:underline">
              Limpar
            </button>
          </div>
        </div>
        <div className="space-y-3">
          {Object.entries(REGIONS).map(([region, ufs]) => {
            const allSelected = ufs.every((uf) => data.ufs_atuacao.includes(uf));
            const someSelected = ufs.some((uf) => data.ufs_atuacao.includes(uf));
            return (
              <div key={region}>
                <button
                  onClick={() => toggleRegion(ufs)}
                  className={`text-sm font-medium mb-1.5 min-h-[44px] px-3 py-2 rounded-lg transition-colors ${
                    allSelected
                      ? "text-[var(--brand-blue)] bg-[var(--brand-blue)]/10"
                      : someSelected
                      ? "text-[var(--ink)] bg-[var(--surface-1)]"
                      : "text-[var(--ink-secondary)]"
                  }`}
                  data-testid={`region-button-${region}`}
                >
                  {region}
                </button>
                <div className="flex flex-wrap gap-1.5">
                  {ufs.map((uf) => (
                    <button
                      key={uf}
                      onClick={() => toggleUf(uf)}
                      className={`min-h-[44px] min-w-[44px] px-3 py-2 text-sm rounded-lg border transition-colors ${
                        data.ufs_atuacao.includes(uf)
                          ? "border-[var(--brand-blue)] bg-[var(--brand-blue)] text-white"
                          : "border-[var(--border)] text-[var(--ink-secondary)] hover:border-[var(--ink-secondary)]"
                      }`}
                      title={UF_NAMES[uf]}
                      data-testid={`uf-button-${uf}`}
                    >
                      {uf}
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {errors.ufs_atuacao && (
        <p id="ufs-error" className="text-xs text-[var(--error)] mt-1" role="alert" data-testid="ufs-error">
          {errors.ufs_atuacao.message}
        </p>
      )}

      {/* COPY-COP-005: Value Range — always visible on desktop, collapsible on mobile */}
      <div className="block sm:block">
        <button
          type="button"
          onClick={() => setShowValueRange(!showValueRange)}
          className="flex sm:hidden items-center gap-2 w-full px-3 py-2 text-sm text-ink-secondary hover:text-ink transition-colors"
          data-testid="value-range-toggle"
        >
          <svg className={`w-4 h-4 transition-transform ${showValueRange ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          Faixa de valor {showValueRange ? '(ocultar)' : '(opcional — padrão R$ 100k a R$ 500k)'}
        </button>
        <div className={`${showValueRange ? 'block' : 'hidden'} sm:block`}>
          <ValueRangeSelector
            valorMin={data.faixa_valor_min}
            valorMax={data.faixa_valor_max}
            onChangeMin={(v) => onChange({ faixa_valor_min: v })}
            onChangeMax={(v) => onChange({ faixa_valor_max: v })}
          />
        </div>
      </div>
      {errors.faixa_valor_max && (
        <p id="valor-error" className="text-xs text-[var(--error)] mt-1" role="alert" data-testid="valor-error">
          {errors.faixa_valor_max.message}
        </p>
      )}
    </div>
  );
}
