"use client";

import { useState, useEffect, useCallback } from "react";

// --- Constants ---

const UF_OPTIONS = [
  "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO",
  "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI", "PR",
  "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
];

const SECTOR_OPTIONS = [
  { value: "construcao_civil", label: "Construção Civil" },
  { value: "engenharia", label: "Engenharia" },
  { value: "engenharia_rodoviaria", label: "Engenharia Rodoviária" },
  { value: "informatica", label: "Informática / TI" },
  { value: "software_desenvolvimento", label: "Desenvolvimento de Software" },
  { value: "manutencao_predial", label: "Manutenção Predial" },
  { value: "servicos_prediais", label: "Serviços Prediais" },
  { value: "medicamentos", label: "Medicamentos" },
  { value: "alimentos", label: "Alimentos" },
  { value: "vigilancia", label: "Vigilância" },
  { value: "transporte_servicos", label: "Transporte" },
];

// --- Interface ---

interface MarketplaceFiltersProps {
  setor: string;
  uf: string;
  onFilterChange: (setor: string, uf: string) => void;
}

// --- Component ---

export function MarketplaceFilters({
  setor,
  uf,
  onFilterChange,
}: MarketplaceFiltersProps) {
  const [localSetor, setLocalSetor] = useState(setor);
  const [localUf, setLocalUf] = useState(uf);

  // Sync external state changes
  useEffect(() => {
    setLocalSetor(setor);
  }, [setor]);

  useEffect(() => {
    setLocalUf(uf);
  }, [uf]);

  const handleApply = useCallback(() => {
    onFilterChange(localSetor, localUf);
  }, [localSetor, localUf, onFilterChange]);

  const handleClear = useCallback(() => {
    setLocalSetor("");
    setLocalUf("");
    onFilterChange("", "");
  }, [onFilterChange]);

  return (
    <div className="flex flex-wrap gap-3 mb-6 p-4 rounded-xl bg-[var(--surface-1)] border border-[var(--border-primary)]">
      {/* Sector filter */}
      <div className="flex-1 min-w-[200px]">
        <label
          htmlFor="filter-setor"
          className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
        >
          Setor
        </label>
        <select
          id="filter-setor"
          value={localSetor}
          onChange={(e) => setLocalSetor(e.target.value)}
          className="w-full rounded-lg border border-[var(--border-primary)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-strong)]"
        >
          <option value="">Todos os setores</option>
          {SECTOR_OPTIONS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
      </div>

      {/* UF filter */}
      <div className="flex-1 min-w-[100px]">
        <label
          htmlFor="filter-uf"
          className="block text-xs font-medium text-[var(--text-secondary)] mb-1"
        >
          UF
        </label>
        <select
          id="filter-uf"
          value={localUf}
          onChange={(e) => setLocalUf(e.target.value)}
          className="w-full rounded-lg border border-[var(--border-primary)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-strong)]"
        >
          <option value="">Todas as UFs</option>
          {UF_OPTIONS.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </select>
      </div>

      {/* Action buttons */}
      <div className="flex items-end gap-2">
        <button
          onClick={handleApply}
          className="px-4 py-2 rounded-lg bg-[var(--accent-strong)] text-white text-sm font-medium hover:opacity-90 transition-opacity"
        >
          Filtrar
        </button>
        {(localSetor || localUf) && (
          <button
            onClick={handleClear}
            className="px-4 py-2 rounded-lg border border-[var(--border-primary)] text-[var(--text-secondary)] text-sm hover:bg-[var(--surface-2)] transition-colors"
          >
            Limpar
          </button>
        )}
      </div>
    </div>
  );
}
