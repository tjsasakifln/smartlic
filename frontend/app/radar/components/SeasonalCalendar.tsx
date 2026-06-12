"use client";

import React, { useState, useMemo } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MesCalendario {
  mes: number;
  volume_medio: number;
  quantidade_media: number;
  setor_dominante: string;
  orgaos_principais: string[];
  indice_sazonalidade: number;
  tendencia: "crescimento" | "estabilidade" | "declinio";
  variacao_anual: number;
}

export interface SeasonalCalendarData {
  calendario: MesCalendario[];
  stats: {
    uf: string;
    anos_analisados: number;
    total_contratos_base: number;
    mes_pico: number | null;
    mes_vale: number | null;
  };
}

export interface SectorSeasonality {
  setor: string;
  meses: MesCalendario[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MONTHS_PT = [
  "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
  "Jul", "Ago", "Set", "Out", "Nov", "Dez",
];

const MONTHS_FULL = [
  "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

function getSeasonalityColor(indice: number, volume: number): string {
  const intensity = Math.min(Math.max(indice * volume / 100000, 0), 1);
  const alpha = 0.1 + intensity * 0.7;
  if (indice > 0.3) {
    return `rgba(34, 139, 34, ${alpha})`;
  }
  if (indice > 0.1) {
    return `rgba(255, 165, 0, ${alpha})`;
  }
  return `rgba(100, 116, 139, ${alpha})`;
}

function getTendenciaIcon(tendencia: string): string {
  switch (tendencia) {
    case "crescimento": return "↑";
    case "declinio": return "↓";
    default: return "→";
  }
}

function formatCurrency(val: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(val);
}

function formatNumber(val: number): string {
  return new Intl.NumberFormat("pt-BR").format(val);
}

function isActiveMonth(mes: number): boolean {
  const now = new Date().getMonth() + 1;
  return mes >= now && mes <= now + 2;
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

const CalendarioTooltip = React.memo(function CalendarioTooltip({
  mes,
  active,
}: {
  mes: MesCalendario | null;
  active: boolean;
}) {
  if (!active || !mes) return null;

  return (
    <div
      className="absolute z-50 bg-[var(--surface-elevated)] border border-[var(--border)] rounded-lg shadow-xl p-4 text-sm min-w-[220px] pointer-events-none"
      role="tooltip"
      data-testid="calendar-tooltip"
    >
      <p className="font-semibold text-[var(--ink)] mb-2">
        {MONTHS_FULL[mes.mes - 1]}
      </p>
      <div className="space-y-1.5 text-[var(--ink-secondary)]">
        <p className="flex justify-between">
          <span>Volume medio</span>
          <span className="font-medium text-[var(--ink)]">{formatCurrency(mes.volume_medio)}</span>
        </p>
        <p className="flex justify-between">
          <span>Quantidade media</span>
          <span className="font-medium text-[var(--ink)]">{formatNumber(mes.quantidade_media)}</span>
        </p>
        <p className="flex justify-between">
          <span>Setor dominante</span>
          <span className="font-medium text-[var(--ink)]">{mes.setor_dominante}</span>
        </p>
        <p className="flex justify-between">
          <span>Indice sazonal</span>
          <span className="font-medium text-[var(--ink)]">{mes.indice_sazonalidade.toFixed(2)}</span>
        </p>
        <p className="flex justify-between">
          <span>Tendencia</span>
          <span className="font-medium text-[var(--ink)]">
            {getTendenciaIcon(mes.tendencia)} {mes.tendencia}
          </span>
        </p>
        {mes.orgaos_principais.length > 0 && (
          <div className="pt-1.5 border-t border-[var(--border)]">
            <p className="text-xs text-[var(--ink-muted)] mb-1">Orgaos principais:</p>
            <ul className="text-xs space-y-0.5">
              {mes.orgaos_principais.slice(0, 3).map((orgao, i) => (
                <li key={i} className="truncate text-[var(--ink)]">{orgao}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// Detail Modal
// ---------------------------------------------------------------------------

function DetailModal({
  mes,
  onClose,
}: {
  mes: MesCalendario;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-label={`Detalhes de ${MONTHS_FULL[mes.mes - 1]}`}
      data-testid="calendar-detail-modal"
    >
      <div
        className="bg-[var(--surface-0)] border border-[var(--border)] rounded-xl shadow-2xl p-6 max-w-md w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-[var(--ink)]">
            {MONTHS_FULL[mes.mes - 1]}
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-[var(--surface-1)] text-[var(--ink-muted)] hover:text-[var(--ink)] transition-colors"
            aria-label="Fechar"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-[var(--surface-1)] rounded-lg p-3">
              <p className="text-xs text-[var(--ink-muted)]">Volume medio</p>
              <p className="text-lg font-bold text-[var(--ink)]">{formatCurrency(mes.volume_medio)}</p>
            </div>
            <div className="bg-[var(--surface-1)] rounded-lg p-3">
              <p className="text-xs text-[var(--ink-muted)]">Quantidade media</p>
              <p className="text-lg font-bold text-[var(--ink)]">{formatNumber(mes.quantidade_media)}</p>
            </div>
          </div>

          <div className="bg-[var(--surface-1)] rounded-lg p-3">
            <p className="text-xs text-[var(--ink-muted)] mb-1">Setor dominante</p>
            <p className="font-medium text-[var(--ink)]">{mes.setor_dominante}</p>
          </div>

          <div className="bg-[var(--surface-1)] rounded-lg p-3">
            <p className="text-xs text-[var(--ink-muted)] mb-2">Orgaos previstos</p>
            {mes.orgaos_principais.length > 0 ? (
              <ul className="space-y-1">
                {mes.orgaos_principais.map((orgao, i) => (
                  <li key={i} className="text-sm text-[var(--ink)] flex items-center gap-2">
                    <span className="w-1.5 h-1.5 rounded-full bg-[var(--brand-blue)] flex-shrink-0" />
                    {orgao}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-[var(--ink-muted)]">Nenhum orgao registrado</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeleton
// ---------------------------------------------------------------------------

function CalendarSkeleton() {
  return (
    <div className="animate-pulse space-y-3" data-testid="calendar-skeleton">
      <div className="h-8 bg-[var(--surface-1)] rounded-lg w-1/3" />
      <div className="grid grid-cols-12 gap-1.5">
        {Array.from({ length: 36 }).map((_, i) => (
          <div key={i} className="h-14 bg-[var(--surface-1)] rounded-lg" />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function CalendarEmpty() {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center"
      data-testid="calendar-empty"
    >
      <div className="w-12 h-12 rounded-full bg-[var(--surface-1)] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-[var(--ink-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
      </div>
      <p className="text-[var(--ink-secondary)] font-medium">Nenhum dado sazonal disponivel</p>
      <p className="text-sm text-[var(--ink-muted)] mt-1">
        Selecione outro filtro ou periodo
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error State
// ---------------------------------------------------------------------------

function CalendarError({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center bg-[var(--surface-1)] rounded-xl"
      data-testid="calendar-error"
    >
      <div className="w-12 h-12 rounded-full bg-[var(--error-bg)] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-[var(--error)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      </div>
      <p className="text-[var(--error)] font-medium">Erro ao carregar dados sazonais</p>
      <button
        onClick={onRetry}
        className="mt-3 px-4 py-2 text-sm font-medium text-[var(--brand-blue)] hover:bg-[var(--surface-2)] rounded-lg transition-colors"
      >
        Tentar novamente
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Filters Sub-component
// ---------------------------------------------------------------------------

function CalendarFilters({
  availableUfs,
  availableSectors,
  selectedUf,
  selectedSectors,
  selectedYear,
  years,
  onUfChange,
  onSectorsChange,
  onYearChange,
}: {
  availableUfs: string[];
  availableSectors: string[];
  selectedUf: string;
  selectedSectors: string[];
  selectedYear: number;
  years: number[];
  onUfChange?: (uf: string) => void;
  onSectorsChange?: (sectors: string[]) => void;
  onYearChange?: (year: number) => void;
}) {
  return (
    <div className="flex flex-wrap gap-3 items-center" data-testid="calendar-filters">
      {onUfChange && availableUfs.length > 0 && (
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-[var(--ink-muted)]">UF:</label>
          <select
            value={selectedUf}
            onChange={(e) => onUfChange(e.target.value)}
            className="px-2 py-1 text-sm bg-[var(--surface-1)] border border-[var(--border)] rounded-lg text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]"
            data-testid="filter-uf"
          >
            <option value="BR">Todas</option>
            {availableUfs.map((uf) => (
              <option key={uf} value={uf}>{uf}</option>
            ))}
          </select>
        </div>
      )}

      {onSectorsChange && availableSectors.length > 0 && (
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-[var(--ink-muted)]">Setor:</label>
          <select
            multiple
            value={selectedSectors}
            onChange={(e) => {
              const values = Array.from(e.target.selectedOptions, (o) => o.value);
              onSectorsChange(values);
            }}
            className="px-2 py-1 text-sm bg-[var(--surface-1)] border border-[var(--border)] rounded-lg text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)] min-w-[140px]"
            data-testid="filter-sectors"
          >
            {availableSectors.map((sector) => (
              <option key={sector} value={sector}>{sector}</option>
            ))}
          </select>
        </div>
      )}

      {onYearChange && (
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-[var(--ink-muted)]">Ano:</label>
          <select
            value={selectedYear}
            onChange={(e) => onYearChange(Number(e.target.value))}
            className="px-2 py-1 text-sm bg-[var(--surface-1)] border border-[var(--border)] rounded-lg text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]"
            data-testid="filter-year"
          >
            {years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface SeasonalCalendarProps {
  data: SectorSeasonality[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  availableUfs?: string[];
  availableSectors?: string[];
  selectedUf?: string;
  selectedSectors?: string[];
  selectedYear?: number;
  onUfChange?: (uf: string) => void;
  onSectorsChange?: (sectors: string[]) => void;
  onYearChange?: (year: number) => void;
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function SeasonalCalendar({
  data,
  loading = false,
  error = null,
  onRetry,
  availableUfs = [],
  availableSectors = [],
  selectedUf = "BR",
  selectedSectors = [],
  selectedYear = new Date().getFullYear(),
  onUfChange,
  onSectorsChange,
  onYearChange,
}: SeasonalCalendarProps) {
  const [hoveredMes, setHoveredMes] = useState<MesCalendario | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [selectedMes, setSelectedMes] = useState<MesCalendario | null>(null);
  const [isMobile, setIsMobile] = useState(false);

  React.useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  if (loading) return <CalendarSkeleton />;
  if (error) return <CalendarError onRetry={onRetry || (() => {})} />;
  if (!data || data.length === 0) return <CalendarEmpty />;

  const years = useMemo(() => {
    const y = new Date().getFullYear();
    return [y - 4, y - 3, y - 2, y - 1, y, y + 1];
  }, []);

  // Mobile: vertical list
  if (isMobile) {
    return (
      <div className="space-y-4" data-testid="seasonal-calendar-mobile">
        <CalendarFilters
          availableUfs={availableUfs}
          availableSectors={availableSectors}
          selectedUf={selectedUf}
          selectedSectors={selectedSectors}
          selectedYear={selectedYear}
          years={years}
          onUfChange={onUfChange}
          onSectorsChange={onSectorsChange}
          onYearChange={onYearChange}
        />
        <div className="space-y-3">
          {data.map((sector) => (
            <div key={sector.setor} className="bg-[var(--surface-1)] rounded-lg p-3">
              <p className="text-sm font-medium text-[var(--ink)] mb-2">{sector.setor}</p>
              {sector.meses.map((mes) => (
                <button
                  key={mes.mes}
                  onClick={() => setSelectedMes(mes)}
                  className="w-full flex items-center justify-between py-1.5 px-2 rounded-md hover:bg-[var(--surface-2)] transition-colors"
                  style={{ backgroundColor: getSeasonalityColor(mes.indice_sazonalidade, mes.volume_medio) }}
                >
                  <span className="text-xs text-[var(--ink)]">{MONTHS_PT[mes.mes - 1]}</span>
                  <span className="text-xs font-medium text-[var(--ink)]">
                    {formatCurrency(mes.volume_medio)}
                  </span>
                </button>
              ))}
            </div>
          ))}
        </div>
        {selectedMes && (
          <DetailModal mes={selectedMes} onClose={() => setSelectedMes(null)} />
        )}
      </div>
    );
  }

  // Desktop: 12-column heatmap grid
  const displaySectors = selectedSectors.length > 0
    ? data.filter((s) => selectedSectors.includes(s.setor))
    : data;

  return (
    <div className="space-y-4" data-testid="seasonal-calendar">
      <CalendarFilters
        availableUfs={availableUfs}
        availableSectors={availableSectors}
        selectedUf={selectedUf}
        selectedSectors={selectedSectors}
        selectedYear={selectedYear}
        years={years}
        onUfChange={onUfChange}
        onSectorsChange={onSectorsChange}
        onYearChange={onYearChange}
      />

      <div className="overflow-x-auto">
        <div className="min-w-[700px]">
          {/* Header row */}
          <div className="grid grid-cols-[160px_repeat(12,_1fr)] gap-1 mb-1">
            <div className="text-xs font-semibold text-[var(--ink-muted)] uppercase tracking-wider px-2 py-1">
              Setor
            </div>
            {MONTHS_PT.map((mes) => (
              <div
                key={mes}
                className="text-xs font-medium text-[var(--ink-muted)] text-center py-1"
              >
                {mes}
              </div>
            ))}
          </div>

          {/* Data rows */}
          <div className="space-y-1">
            {displaySectors.map((sector) => (
              <div
                key={sector.setor}
                className="grid grid-cols-[160px_repeat(12,_1fr)] gap-1"
              >
                <div className="flex items-center px-2 py-1">
                  <span className="text-xs font-medium text-[var(--ink-secondary)] truncate">
                    {sector.setor}
                  </span>
                </div>
                {sector.meses.map((mes) => {
                  const active = isActiveMonth(mes.mes);
                  return (
                    <button
                      key={mes.mes}
                      className={`relative h-10 rounded-md transition-all duration-150 hover:scale-105 hover:shadow-md cursor-pointer ${
                        active ? "ring-2 ring-[var(--brand-blue)]" : ""
                      }`}
                      style={{
                        backgroundColor: getSeasonalityColor(mes.indice_sazonalidade, mes.volume_medio),
                      }}
                      onMouseEnter={(e) => {
                        const rect = e.currentTarget.getBoundingClientRect();
                        setTooltipPos({ x: rect.left, y: rect.top - 8 });
                        setHoveredMes(mes);
                      }}
                      onMouseLeave={() => setHoveredMes(null)}
                      onClick={() => setSelectedMes(mes)}
                      aria-label={`${MONTHS_FULL[mes.mes - 1]}: ${formatCurrency(mes.volume_medio)}`}
                      data-month={mes.mes}
                    />
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Floating tooltip */}
      {hoveredMes && (
        <div style={{ position: "fixed", left: tooltipPos.x, top: tooltipPos.y, transform: "translateY(-100%)" }}>
          <CalendarioTooltip mes={hoveredMes} active />
        </div>
      )}

      {/* Detail modal */}
      {selectedMes && (
        <DetailModal mes={selectedMes} onClose={() => setSelectedMes(null)} />
      )}
    </div>
  );
}
