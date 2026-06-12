"use client";

/**
 * RegionalDependencyMap — SUBINTEL-012 (#1681)
 *
 * Brazil SVG map heatmap showing regional dependency index for a sector.
 *
 * - UFs colored by contract intensity (green = high, red = low)
 * - Tooltip on hover with UF, contract count, total value, percentage
 * - Dependency index bar with visual scale
 * - Risk classification: Baixo (green), Medio (yellow), Alto (red)
 * - Table with top UFs sorted by contract count
 * - CTA for non-paying users
 *
 * Usage:
 *   <RegionalDependencyMap sectorId="engenharia" />
 *   <RegionalDependencyMap sectorId="engenharia" isPremiumUser={true} />
 */
import { useEffect, useState } from "react";
import mixpanel from "mixpanel-browser";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RegionalDependencyItem {
  uf: string;
  dependency_score: number;
  contract_count: number;
  total_value: number;
}

interface RegionalDependencyData {
  sector_id: string;
  uf_distribution: RegionalDependencyItem[];
  total_contracts: number;
  total_value: number;
  coverage_ufs: number;
  hhi_normalized: number;
  risk_level: string;
  disclaimer: string;
  generated_at: string;
}

export interface RegionalDependencyMapProps {
  /** Sector ID from sectors_data.yaml (e.g., "engenharia") */
  sectorId: string;
  /** Whether the user has a premium plan */
  isPremiumUser?: boolean;
  /** Upgrade URL for CTA */
  upgradeUrl?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ALL_UFS = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO",
  "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI",
  "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

// Simplified Brazil SVG paths for each UF (approximate center positions for tooltip)
const UF_COORDS: Record<string, { x: number; y: number }> = {
  AC: { x: 15, y: 55 }, AL: { x: 52, y: 60 }, AP: { x: 70, y: 15 },
  AM: { x: 30, y: 30 }, BA: { x: 55, y: 50 }, CE: { x: 55, y: 27 },
  DF: { x: 42, y: 48 }, ES: { x: 57, y: 53 }, GO: { x: 40, y: 45 },
  MA: { x: 48, y: 30 }, MT: { x: 30, y: 45 }, MS: { x: 28, y: 55 },
  MG: { x: 48, y: 52 }, PA: { x: 60, y: 25 }, PB: { x: 55, y: 32 },
  PR: { x: 42, y: 62 }, PE: { x: 53, y: 35 }, PI: { x: 50, y: 30 },
  RJ: { x: 55, y: 56 }, RN: { x: 57, y: 28 }, RS: { x: 32, y: 70 },
  RO: { x: 22, y: 50 }, RR: { x: 50, y: 10 }, SC: { x: 42, y: 65 },
  SP: { x: 48, y: 58 }, SE: { x: 54, y: 55 }, TO: { x: 42, y: 38 },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmtBRL(value: number): string {
  if (value >= 1_000_000_000) {
    return `R$ ${(value / 1_000_000_000).toFixed(1).replace(".", ",")} bi`;
  }
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toFixed(1).replace(".", ",")} mi`;
  }
  return `R$ ${value.toLocaleString("pt-BR")}`;
}

function getRiskColor(riskLevel: string): string {
  switch (riskLevel) {
    case "baixo": return "text-green-600";
    case "medio": return "text-yellow-600";
    case "alto": return "text-red-600";
    default: return "text-gray-500";
  }
}

function getRiskBg(riskLevel: string): string {
  switch (riskLevel) {
    case "baixo": return "bg-green-100 border-green-300";
    case "medio": return "bg-yellow-100 border-yellow-300";
    case "alto": return "bg-red-100 border-red-300";
    default: return "bg-gray-100 border-gray-300";
  }
}

function getUfColor(score: number): string {
  if (score >= 30) return "#166534"; // dark green
  if (score >= 15) return "#22c55e"; // green
  if (score >= 8) return "#eab308";  // yellow
  if (score >= 3) return "#f97316";  // orange
  return "#ef4444";                   // red
}

function getUfOpacity(score: number): number {
  if (score <= 0) return 0.15;
  return Math.min(0.3 + (score / 100) * 0.7, 1.0);
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function RegionalDependencyMap({
  sectorId,
  isPremiumUser = false,
  upgradeUrl = "/planos",
}: RegionalDependencyMapProps) {
  const [data, setData] = useState<RegionalDependencyData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredUf, setHoveredUf] = useState<string | null>(null);
  const [tooltipPos, setTooltipPos] = useState({ x: 0, y: 0 });

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`/api/subcontract/regional-dependency?setor=${sectorId}`);
        if (!res.ok) {
          if (res.status === 404 || res.status === 403) {
            setData(null);
            return;
          }
          throw new Error(`HTTP ${res.status}`);
        }
        const json: RegionalDependencyData = await res.json();
        if (!cancelled) {
          setData(json);
          mixpanel.track("subcontract_regional_dependency_viewed", {
            sector_id: sectorId,
            coverage_ufs: json.coverage_ufs,
            risk_level: json.risk_level,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Erro ao carregar dados");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchData();
    return () => { cancelled = true; };
  }, [sectorId]);

  // --- Loading state ---
  if (loading) {
    return (
      <div className="animate-pulse rounded-lg border border-gray-200 p-4">
        <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="h-48 bg-gray-200 rounded mb-4"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
      </div>
    );
  }

  // --- Gate closed (no access) ---
  if (!data && !error) {
    return (
      <div className="rounded-lg border border-blue-200 bg-blue-50 p-6 text-center">
        <h3 className="text-lg font-semibold text-blue-800 mb-2">
          Indice de Dependencia Regional
        </h3>
        <p className="text-sm text-blue-600 mb-4">
          Visualize a distribuicao geografica dos contratos do setor e identifique
          oportunidades de expansao regional.
        </p>
        <button
          onClick={() => {
            mixpanel.track("subcontract_regional_cta", { sector_id: sectorId });
            window.location.href = upgradeUrl;
          }}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          SmartLic Insight — Desbloquear
        </button>
      </div>
    );
  }

  // --- Error state ---
  if (error || !data) {
    return null; // Silently fail for pSEO additivity
  }

  const ufMap = new Map(data.uf_distribution.map((d) => [d.uf, d]));
  const riskColor = getRiskColor(data.risk_level);
  const riskBg = getRiskBg(data.risk_level);
  const riskLabel =
    data.risk_level === "baixo"
      ? "Baixo — setor distribuido geograficamente"
      : data.risk_level === "medio"
      ? "Medio — concentracao moderada"
      : data.risk_level === "alto"
      ? "Alto — alta concentracao regional"
      : "Indisponivel";

  return (
    <div
      className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6"
      data-regional-dependency-map
    >
      <h3 className="text-lg font-semibold text-gray-900 mb-1">
        Indice de Dependencia Regional
      </h3>
      <p className="text-sm text-gray-500 mb-4">
        Distribuicao de contratos do setor <strong>{data.sector_id}</strong> por UF
      </p>

      {/* Risk badge */}
      <div className={`inline-block rounded px-3 py-1 text-sm font-medium border ${riskBg} ${riskColor} mb-4`}>
        Risco: {riskLabel}
      </div>

      {/* Dependency index bar */}
      <div className="mb-4">
        <div className="flex justify-between text-xs text-gray-500 mb-1">
          <span>Alta dependencia</span>
          <span>Distribuido</span>
        </div>
        <div className="h-3 rounded-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 relative">
          <div
            className="absolute top-[-4px] w-2 h-5 bg-black rounded-full"
            style={{ left: `${Math.min(data.hhi_normalized * 100, 100)}%` }}
            title={`HHI: ${(data.hhi_normalized * 100).toFixed(0)}%`}
          />
        </div>
        <div className="text-xs text-gray-500 mt-1 text-center">
          Indice: {(data.hhi_normalized * 100).toFixed(0)}% distribuido
        </div>
      </div>

      {/* Brazil SVG Map */}
      <div className="relative mb-4" style={{ maxWidth: "400px", margin: "0 auto" }}>
        <svg viewBox="0 0 85 85" className="w-full h-auto" role="img" aria-label="Mapa do Brasil com dependencia regional">
          {ALL_UFS.map((uf) => {
            const ufData = ufMap.get(uf);
            const score = ufData?.dependency_score ?? 0;
            const coords = UF_COORDS[uf];
            return (
              <g key={uf}>
                <circle
                  cx={coords.x}
                  cy={coords.y}
                  r={Math.max(2, score * 0.15)}
                  fill={getUfColor(score)}
                  opacity={getUfOpacity(score)}
                  className="cursor-pointer transition-opacity hover:opacity-80"
                  onMouseEnter={(e) => {
                    setHoveredUf(uf);
                    setTooltipPos({ x: e.clientX, y: e.clientY });
                  }}
                  onMouseMove={(e) => {
                    setTooltipPos({ x: e.clientX, y: e.clientY });
                  }}
                  onMouseLeave={() => setHoveredUf(null)}
                />
                <text
                  x={coords.x}
                  y={coords.y + 1}
                  textAnchor="middle"
                  fontSize="2.5"
                  fill={score > 0 ? "white" : "#999"}
                  fontWeight="bold"
                  className="pointer-events-none select-none"
                >
                  {uf}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Tooltip */}
        {hoveredUf && ufMap.has(hoveredUf) && (
          <div
            className="absolute z-10 rounded-lg bg-gray-900 px-3 py-2 text-xs text-white shadow-lg pointer-events-none"
            style={{
              left: Math.min(tooltipPos.x - 80, window.innerWidth - 200),
              top: tooltipPos.y - 80,
            }}
          >
            <p className="font-semibold">{hoveredUf}</p>
            <p>Contratos: {ufMap.get(hoveredUf)!.contract_count}</p>
            <p>Valor: {fmtBRL(ufMap.get(hoveredUf)!.total_value)}</p>
            <p>Participacao: {ufMap.get(hoveredUf)!.dependency_score}%</p>
          </div>
        )}
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <div className="rounded bg-gray-50 p-2 text-center">
          <p className="text-lg font-bold text-gray-900">{data.total_contracts}</p>
          <p className="text-xs text-gray-500">Contratos</p>
        </div>
        <div className="rounded bg-gray-50 p-2 text-center">
          <p className="text-lg font-bold text-gray-900">{fmtBRL(data.total_value)}</p>
          <p className="text-xs text-gray-500">Valor Total</p>
        </div>
        <div className="rounded bg-gray-50 p-2 text-center">
          <p className="text-lg font-bold text-gray-900">{data.coverage_ufs}/27</p>
          <p className="text-xs text-gray-500">UFs com contratos</p>
        </div>
        <div className="rounded bg-gray-50 p-2 text-center">
          <p className={`text-lg font-bold ${riskColor}`}>
            {((1 - data.hhi_normalized) * 100).toFixed(0)}%
          </p>
          <p className="text-xs text-gray-500">Concentracao HHI</p>
        </div>
      </div>

      {/* Top UFs table */}
      {data.uf_distribution.length > 0 && (
        <div className="overflow-x-auto mb-4">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs text-gray-500 uppercase">
                <th className="pb-2 font-medium">UF</th>
                <th className="pb-2 font-medium text-right">Contratos</th>
                <th className="pb-2 font-medium text-right">Valor</th>
                <th className="pb-2 font-medium text-right">%</th>
              </tr>
            </thead>
            <tbody>
              {data.uf_distribution.slice(0, 10).map((item) => (
                <tr key={item.uf} className="border-b border-gray-100">
                  <td className="py-1.5 font-medium">{item.uf}</td>
                  <td className="py-1.5 text-right">{item.contract_count}</td>
                  <td className="py-1.5 text-right">{fmtBRL(item.total_value)}</td>
                  <td className="py-1.5 text-right">{item.dependency_score}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Disclaimer */}
      <p className="text-xs text-gray-400 italic">{data.disclaimer}</p>
    </div>
  );
}
