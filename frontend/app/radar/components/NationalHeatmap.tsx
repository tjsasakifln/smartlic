"use client";

import React, { useState, useMemo } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface UfHeatmapData {
  uf: string;
  volume_previsto: number;
  quantidade_prevista: number;
  orgaos_principais: string[];
  categorias_principais: string[];
  valor_estimado: number;
  confidence: number;
}

export interface NationalHeatmapProps {
  data: UfHeatmapData[];
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  selectedSectors?: string[];
  availableSectors?: string[];
  selectedMes?: number;
  onSectorChange?: (sectors: string[]) => void;
  onMesChange?: (mes: number) => void;
  onUfClick?: (uf: string) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALL_UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
  "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
  "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

const MONTHS_PT = [
  "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

function getHeatColor(volume: number, maxVolume: number): string {
  if (maxVolume === 0) return "var(--surface-1)";
  const ratio = volume / maxVolume;
  if (ratio === 0) return "var(--surface-1)";
  if (ratio < 0.1) return "rgba(34, 139, 34, 0.15)";
  if (ratio < 0.25) return "rgba(34, 139, 34, 0.3)";
  if (ratio < 0.5) return "rgba(34, 139, 34, 0.5)";
  if (ratio < 0.75) return "rgba(34, 139, 34, 0.7)";
  return "rgba(34, 139, 34, 0.9)";
}

function getConfidenceLabel(confidence: number): string {
  if (confidence >= 80) return "Alta";
  if (confidence >= 50) return "Media";
  return "Baixa";
}

function getConfidenceColor(confidence: number): string {
  if (confidence >= 80) return "var(--success)";
  if (confidence >= 50) return "var(--warning)";
  return "var(--ink-muted)";
}

// ---------------------------------------------------------------------------
// Brazil SVG Paths (simplified state coordinates)
// ---------------------------------------------------------------------------

const BRAZIL_STATE_PATHS: Record<string, string> = {
  AC: "M100,280 L120,275 L130,290 L125,310 L105,315 L95,300 Z",
  AL: "M175,345 L190,340 L195,355 L180,360 Z",
  AP: "M140,190 L160,185 L165,200 L150,210 L135,205 Z",
  AM: "M80,240 L120,230 L130,245 L125,270 L100,275 L85,260 Z",
  BA: "M170,310 L190,305 L200,320 L195,340 L175,345 L165,330 Z",
  CE: "M165,280 L185,275 L190,290 L175,300 L160,295 Z",
  DF: "M220,320 L225,315 L230,320 L225,325 Z",
  ES: "M235,340 L245,335 L250,350 L240,355 Z",
  GO: "M200,290 L220,285 L225,310 L215,325 L200,320 L195,305 Z",
  MA: "M155,260 L175,255 L180,270 L170,285 L155,280 Z",
  MT: "M175,240 L200,235 L205,260 L195,285 L180,285 L170,265 Z",
  MS: "M190,290 L210,285 L215,310 L205,330 L195,330 L190,310 Z",
  MG: "M210,310 L230,305 L235,330 L240,355 L220,360 L205,345 L205,325 Z",
  PA: "M130,210 L165,200 L175,220 L170,245 L155,255 L135,250 L125,230 Z",
  PB: "M180,320 L192,315 L195,330 L182,335 Z",
  PR: "M205,370 L230,365 L235,385 L225,395 L210,390 L200,380 Z",
  PE: "M175,310 L190,305 L195,320 L192,330 L180,330 L170,320 Z",
  PI: "M155,280 L170,275 L175,290 L165,300 L155,295 Z",
  RJ: "M235,355 L248,350 L252,365 L240,370 Z",
  RN: "M178,305 L192,300 L195,314 L180,318 Z",
  RS: "M200,405 L230,400 L240,420 L225,435 L210,430 L195,420 Z",
  RO: "M95,260 L115,255 L120,270 L110,285 L95,280 Z",
  RR: "M100,195 L115,190 L120,205 L108,210 Z",
  SC: "M210,380 L232,375 L235,395 L225,405 L215,400 L205,390 Z",
  SP: "M210,350 L235,345 L240,365 L230,370 L215,365 L205,355 Z",
  SE: "M180,340 L192,335 L195,350 L182,352 Z",
  TO: "M140,230 L165,220 L170,240 L160,255 L145,250 L135,240 Z",
};

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

const HeatmapTooltip = React.memo(function HeatmapTooltip({
  data,
  active,
}: {
  data: UfHeatmapData | null;
  active: boolean;
}) {
  if (!active || !data) return null;

  return (
    <div
      className="bg-[var(--surface-elevated)] border border-[var(--border)] rounded-lg shadow-xl p-4 text-sm min-w-[200px] pointer-events-none"
      role="tooltip"
      data-testid="heatmap-tooltip"
    >
      <p className="font-semibold text-lg text-[var(--ink)] mb-2">{data.uf}</p>
      <div className="space-y-1.5 text-[var(--ink-secondary)]">
        <p className="flex justify-between">
          <span>Volume previsto</span>
          <span className="font-medium text-[var(--ink)]">{formatCurrency(data.volume_previsto)}</span>
        </p>
        <p className="flex justify-between">
          <span>Quantidade prevista</span>
          <span className="font-medium text-[var(--ink)]">{formatNumber(data.quantidade_prevista)}</span>
        </p>
        <p className="flex justify-between">
          <span>Valor estimado</span>
          <span className="font-medium text-[var(--ink)]">{formatCurrency(data.valor_estimado)}</span>
        </p>
        <p className="flex justify-between">
          <span>Confianca</span>
          <span className="font-medium" style={{ color: getConfidenceColor(data.confidence) }}>
            {getConfidenceLabel(data.confidence)} ({data.confidence.toFixed(0)}%)
          </span>
        </p>
        {data.orgaos_principais.length > 0 && (
          <div className="pt-1.5 border-t border-[var(--border)]">
            <p className="text-xs text-[var(--ink-muted)] mb-1">Orgaos principais:</p>
            <ul className="text-xs space-y-0.5">
              {data.orgaos_principais.slice(0, 3).map((orgao, i) => (
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
// Loading Skeleton
// ---------------------------------------------------------------------------

function MapSkeleton() {
  return (
    <div className="animate-pulse" data-testid="heatmap-skeleton">
      <div className="w-full aspect-[3/4] max-w-[500px] mx-auto bg-[var(--surface-1)] rounded-xl" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State
// ---------------------------------------------------------------------------

function MapEmpty() {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center"
      data-testid="heatmap-empty"
    >
      <div className="w-12 h-12 rounded-full bg-[var(--surface-1)] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-[var(--ink-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
        </svg>
      </div>
      <p className="text-[var(--ink-secondary)] font-medium">Nenhum dado de heatmap disponivel</p>
      <p className="text-sm text-[var(--ink-muted)] mt-1">
        Selecione um setor ou mes para visualizar
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Error State
// ---------------------------------------------------------------------------

function MapError({ onRetry }: { onRetry: () => void }) {
  return (
    <div
      className="flex flex-col items-center justify-center py-12 text-center bg-[var(--surface-1)] rounded-xl"
      data-testid="heatmap-error"
    >
      <div className="w-12 h-12 rounded-full bg-[var(--error-bg)] flex items-center justify-center mb-3">
        <svg className="w-6 h-6 text-[var(--error)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
        </svg>
      </div>
      <p className="text-[var(--error)] font-medium">Erro ao carregar mapa de calor</p>
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
// Mobile Ranked List
// ---------------------------------------------------------------------------

function MobileRankedList({
  data,
  onUfClick,
}: {
  data: UfHeatmapData[];
  onUfClick?: (uf: string) => void;
}) {
  const sorted = [...data].sort((a, b) => b.volume_previsto - a.volume_previsto);
  const maxVolume = Math.max(...data.map((d) => d.volume_previsto), 1);

  return (
    <div className="space-y-2" data-testid="heatmap-ranked-list">
      {sorted.map((item, i) => (
        <button
          key={item.uf}
          onClick={() => onUfClick?.(item.uf)}
          className="w-full flex items-center gap-3 p-3 bg-[var(--surface-1)] rounded-lg hover:bg-[var(--surface-2)] transition-colors text-left"
        >
          <span className="text-sm font-bold text-[var(--ink-muted)] w-5">{i + 1}</span>
          <span className="text-sm font-semibold text-[var(--ink)] w-8">{item.uf}</span>
          <div className="flex-1">
            <div className="h-2 rounded-full bg-[var(--surface-2)] overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{
                  width: `${(item.volume_previsto / maxVolume) * 100}%`,
                  backgroundColor: getHeatColor(item.volume_previsto, maxVolume),
                }}
              />
            </div>
          </div>
          <span className="text-sm font-medium text-[var(--ink-secondary)]">
            {formatCurrency(item.volume_previsto)}
          </span>
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function NationalHeatmap({
  data,
  loading = false,
  error = null,
  onRetry,
  selectedSectors = [],
  availableSectors = [],
  selectedMes,
  onSectorChange,
  onMesChange,
  onUfClick,
}: NationalHeatmapProps) {
  const [hoveredUf, setHoveredUf] = useState<string | null>(null);
  const [tooltipData, setTooltipData] = useState<UfHeatmapData | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });
  const [isMobile, setIsMobile] = useState(false);

  React.useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  if (loading) return <MapSkeleton />;
  if (error) return <MapError onRetry={onRetry || (() => {})} />;
  if (!data || data.length === 0) return <MapEmpty />;

  const maxVolume = Math.max(...data.map((d) => d.volume_previsto), 1);

  const ufMap = useMemo(() => {
    const map: Record<string, UfHeatmapData> = {};
    data.forEach((d) => { map[d.uf] = d; });
    // Ensure all UFs exist (even with zero data)
    ALL_UFS.forEach((uf) => {
      if (!map[uf]) {
        map[uf] = {
          uf,
          volume_previsto: 0,
          quantidade_prevista: 0,
          orgaos_principais: [],
          categorias_principais: [],
          valor_estimado: 0,
          confidence: 0,
        };
      }
    });
    return map;
  }, [data]);

  const handleUfHover = (uf: string, e: React.MouseEvent) => {
    setHoveredUf(uf);
    setTooltipData(ufMap[uf] || null);
    const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
    setTooltipPos({ x: rect.left + rect.width / 2, y: rect.top });
  };

  const handleUfLeave = () => {
    setHoveredUf(null);
    setTooltipData(null);
  };

  // Mobile: ranked list fallback
  if (isMobile) {
    return (
      <div className="space-y-4" data-testid="national-heatmap-mobile">
        <MapFilters
          availableSectors={availableSectors}
          selectedSectors={selectedSectors}
          selectedMes={selectedMes}
          onSectorChange={onSectorChange}
          onMesChange={onMesChange}
        />
        <MobileRankedList data={data} onUfClick={onUfClick} />
      </div>
    );
  }

  return (
    <div className="space-y-4" data-testid="national-heatmap">
      <MapFilters
        availableSectors={availableSectors}
        selectedSectors={selectedSectors}
        selectedMes={selectedMes}
        onSectorChange={onSectorChange}
        onMesChange={onMesChange}
      />

      <div className="relative flex justify-center">
        {/* SVG Map */}
        <svg
          viewBox="70 180 200 270"
          className="w-full max-w-[500px] h-auto"
          role="img"
          aria-label="Mapa de calor do Brasil por intensidade de demanda"
          data-testid="brazil-heatmap-svg"
        >
          {ALL_UFS.map((uf) => {
            const ufData = ufMap[uf];
            const hasData = ufData && ufData.volume_previsto > 0;
            const pathD = BRAZIL_STATE_PATHS[uf];

            if (!pathD) return null;

            return (
              <path
                key={uf}
                d={pathD}
                fill={hasData ? getHeatColor(ufData.volume_previsto, maxVolume) : "var(--surface-1)"}
                stroke="var(--border)"
                strokeWidth={1.5}
                className={`transition-all duration-150 cursor-pointer ${
                  hoveredUf === uf ? "stroke-[var(--brand-blue)] stroke-2 drop-shadow-md" : ""
                }`}
                onMouseEnter={(e) => handleUfHover(uf, e)}
                onMouseLeave={handleUfLeave}
                onClick={() => onUfClick?.(uf)}
                role="button"
                aria-label={`${uf}: ${ufData ? formatCurrency(ufData.volume_previsto) : "Sem dados"}`}
                data-uf={uf}
              />
            );
          })}

          {/* UF labels (state codes) */}
          {ALL_UFS.map((uf) => {
            const pathD = BRAZIL_STATE_PATHS[uf];
            if (!pathD) return null;
            return (
              <text
                key={`label-${uf}`}
                className="text-[6px] fill-[var(--ink-secondary)] pointer-events-none select-none"
                x={getPathCenter(pathD).x}
                y={getPathCenter(pathD).y}
                textAnchor="middle"
                dominantBaseline="central"
                fontWeight="bold"
              >
                {uf}
              </text>
            );
          })}
        </svg>

        {/* Floating tooltip */}
        {hoveredUf && tooltipData && (
          <div
            style={{
              position: "fixed",
              left: tooltipPos.x,
              top: tooltipPos.y - 8,
              transform: "translate(-50%, -100%)",
            }}
          >
            <HeatmapTooltip data={tooltipData} active />
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-3 text-xs text-[var(--ink-muted)]">
        <span>Baixa</span>
        <div className="flex gap-0.5">
          {[0.15, 0.3, 0.5, 0.7, 0.9].map((opacity) => (
            <div
              key={opacity}
              className="w-4 h-3 rounded-sm"
              style={{ backgroundColor: `rgba(34, 139, 34, ${opacity})` }}
            />
          ))}
        </div>
        <span>Alta</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper: extract centroid from SVG path string (approximate)
// ---------------------------------------------------------------------------

function getPathCenter(d: string): { x: number; y: number } {
  const nums = d.match(/[\d.]+/g);
  if (!nums || nums.length < 2) return { x: 180, y: 300 };
  let sumX = 0; let sumY = 0; let count = 0;
  for (let i = 0; i < nums.length - 1; i += 2) {
    sumX += parseFloat(nums[i]);
    sumY += parseFloat(nums[i + 1]);
    count++;
  }
  if (count === 0) return { x: 180, y: 300 };
  return { x: sumX / count, y: sumY / count };
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

function MapFilters({
  availableSectors,
  selectedSectors,
  selectedMes,
  onSectorChange,
  onMesChange,
}: {
  availableSectors: string[];
  selectedSectors: string[];
  selectedMes?: number;
  onSectorChange?: (sectors: string[]) => void;
  onMesChange?: (mes: number) => void;
}) {
  return (
    <div className="flex flex-wrap gap-3 items-center" data-testid="heatmap-filters">
      {onSectorChange && availableSectors.length > 0 && (
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-[var(--ink-muted)]">Setor:</label>
          <select
            multiple
            value={selectedSectors}
            onChange={(e) => {
              const values = Array.from(e.target.selectedOptions, (o) => o.value);
              onSectorChange(values);
            }}
            className="px-2 py-1 text-sm bg-[var(--surface-1)] border border-[var(--border)] rounded-lg text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)] min-w-[140px]"
            data-testid="heatmap-filter-sectors"
          >
            {availableSectors.map((sector) => (
              <option key={sector} value={sector}>{sector}</option>
            ))}
          </select>
        </div>
      )}

      {onMesChange && (
        <div className="flex items-center gap-2">
          <label className="text-xs font-medium text-[var(--ink-muted)]">Mes:</label>
          <select
            value={selectedMes ?? new Date().getMonth()}
            onChange={(e) => onMesChange(Number(e.target.value))}
            className="px-2 py-1 text-sm bg-[var(--surface-1)] border border-[var(--border)] rounded-lg text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]"
            data-testid="heatmap-filter-mes"
          >
            {MONTHS_PT.map((mes, i) => (
              <option key={i} value={i}>{mes}</option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
