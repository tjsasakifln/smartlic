"use client";

import { X } from "lucide-react";

const TIPO_OPTIONS = [
  { value: "publicacao", label: "Publicacao" },
  { value: "alteracao", label: "Alteracao" },
  { value: "impugnacao", label: "Impugnacao" },
  { value: "esclarecimento", label: "Esclarecimento" },
  { value: "resultado", label: "Resultado" },
  { value: "homologacao", label: "Homologacao" },
  { value: "nota_manual", label: "Notas" },
  { value: "lembrete", label: "Lembretes" },
];

interface TimelineFiltrosProps {
  selectedTipos: string[];
  onToggleTipo: (tipo: string) => void;
  apenasCriticos: boolean;
  onToggleCriticos: () => void;
  dataInicio: string;
  onDataInicioChange: (val: string) => void;
  dataFim: string;
  onDataFimChange: (val: string) => void;
}

export function TimelineFiltros({
  selectedTipos,
  onToggleTipo,
  apenasCriticos,
  onToggleCriticos,
  dataInicio,
  onDataInicioChange,
  dataFim,
  onDataFimChange,
}: TimelineFiltrosProps) {
  const hasActiveFilters =
    selectedTipos.length > 0 || apenasCriticos || dataInicio || dataFim;

  return (
    <div className="space-y-3">
      {/* Chips de tipo */}
      <div className="flex flex-wrap gap-2">
        {TIPO_OPTIONS.map((opt) => {
          const isSelected = selectedTipos.includes(opt.value);
          return (
            <button
              key={opt.value}
              onClick={() => onToggleTipo(opt.value)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                isSelected
                  ? "bg-[var(--brand-blue)] text-white"
                  : "bg-[var(--surface-2)] text-[var(--ink-secondary)] hover:bg-[var(--surface-3)]"
              }`}
            >
              {opt.label}
            </button>
          );
        })}
      </div>

      {/* Controles adicionais */}
      <div className="flex flex-wrap items-center gap-4">
        {/* Toggle apenas criticos */}
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={apenasCriticos}
            onChange={onToggleCriticos}
            className="w-4 h-4 rounded border-gray-300"
          />
          <span className="text-sm text-[var(--ink-secondary)]">
            Apenas criticos
          </span>
        </label>

        {/* Date range */}
        <div className="flex items-center gap-2">
          <label className="text-xs text-[var(--ink-tertiary)]">De:</label>
          <input
            type="date"
            value={dataInicio}
            onChange={(e) => onDataInicioChange(e.target.value)}
            className="px-2 py-1 text-xs border rounded-md bg-[var(--surface-1)] text-[var(--ink)]"
          />
          <label className="text-xs text-[var(--ink-tertiary)]">Ate:</label>
          <input
            type="date"
            value={dataFim}
            onChange={(e) => onDataFimChange(e.target.value)}
            className="px-2 py-1 text-xs border rounded-md bg-[var(--surface-1)] text-[var(--ink)]"
          />
        </div>

        {/* Limpar filtros */}
        {hasActiveFilters && (
          <button
            onClick={() => {
              selectedTipos.forEach(onToggleTipo);
              onToggleCriticos();
              onDataInicioChange("");
              onDataFimChange("");
            }}
            className="text-xs text-[var(--brand-blue)] hover:underline flex items-center gap-1"
          >
            <X size={12} />
            Limpar filtros
          </button>
        )}
      </div>
    </div>
  );
}
