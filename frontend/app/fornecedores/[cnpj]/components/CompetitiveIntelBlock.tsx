"use client";

/**
 * COMPINT-011 (#1663): Competitive Intel Block for /fornecedores/[cnpj].
 *
 * Additive block at the bottom of the supplier profile page showing
 * competitive positioning data (territory expansion, market share,
 * ticket comparison) when the viewing user has the
 * allow_competitive_intel capability.
 *
 * Silent component: renders nothing when the user is not authenticated
 * or does not have the capability (no placeholder, no upgrade message).
 */

import { useEffect, useState } from "react";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Types (mirrors backend response)
// ---------------------------------------------------------------------------

interface ConcorrenteInfo {
  cnpj: string;
  nome: string;
  total_contratos: number;
  ticket_medio: number;
  ticket_mediana: number;
  valor_total_contratado: number;
}

interface TerritorioEntry {
  uf: string;
  contratos: number;
  valor_total: number;
  ticket_medio_uf: number;
  market_share_uf?: number | null;
  tendencia?: string | null;
}

interface OrgaoFavorito {
  orgao_nome: string;
  contratos: number;
  valor_total: number;
  ultima_vitoria?: string | null;
}

interface TerritorioStats {
  ufs_atuacao: number;
  orgaos_unicos: number;
  anos_atuacao: number;
  crescimento_anual?: number | null;
  tendencia_posicionamento?: string | null;
}

interface WinMetrics {
  taxa_vitoria_estimada?: number | null;
  velocidade_crescimento?: number | null;
  tendencia?: string | null;
  ticket_p50?: number | null;
  ticket_p75?: number | null;
}

interface AlertaPosicionamento {
  tipo: string;
  mensagem: string;
  severidade: string;
}

interface IntelData {
  concorrente: ConcorrenteInfo;
  territorio: TerritorioEntry[];
  orgaos_favoritos: OrgaoFavorito[];
  stats: TerritorioStats;
  win_metrics?: WinMetrics | null;
  alertas: AlertaPosicionamento[];
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface CompetitiveIntelBlockProps {
  cnpj: string;
}

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

function fmtBRL(value: number): string {
  if (value >= 1_000_000_000) {
    return `R$ ${(value / 1_000_000_000).toFixed(1).replace(".", ",")} bi`;
  }
  if (value >= 1_000_000) {
    return `R$ ${(value / 1_000_000).toFixed(1).replace(".", ",")} mi`;
  }
  if (value >= 1_000) {
    return `R$ ${(value / 1_000).toFixed(0)} mil`;
  }
  return `R$ ${value.toFixed(0)}`;
}

// ---------------------------------------------------------------------------
// Severity mapping
// ---------------------------------------------------------------------------

const ALERT_STYLES: Record<string, string> = {
  success: "bg-green-50 border-green-200 text-green-800",
  warning: "bg-amber-50 border-amber-200 text-amber-800",
  info: "bg-blue-50 border-blue-200 text-blue-800",
};

const ALERT_ICONS: Record<string, string> = {
  expansao: "\u{1F30D}",        // globe
  crescimento: "\u{1F4C8}",      // chart with up trend
  dominio: "\u{1F3C6}",          // trophy
  novo_entrante: "\u{1F680}",    // rocket
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CompetitiveIntelBlock({
  cnpj,
}: CompetitiveIntelBlockProps) {
  const [data, setData] = useState<IntelData | null>(null);
  const [loading, setLoading] = useState(true);
  const [hasAccess, setHasAccess] = useState<boolean | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

    fetch(`${BACKEND_URL}/v1/intel-concorrente/fornecedor/${encodeURIComponent(cnpj)}`, {
      credentials: "include",
      signal: controller.signal,
      headers: { "Accept": "application/json" },
    })
      .then((res) => {
        if (res.status === 401 || res.status === 403 || res.status === 404) {
          setHasAccess(false);
          setData(null);
          return null;
        }
        if (!res.ok) {
          setHasAccess(false);
          setData(null);
          return null;
        }
        setHasAccess(true);
        return res.json();
      })
      .then((json: IntelData | null) => {
        if (json) setData(json);
      })
      .catch(() => {
        // Silently fail — component renders nothing on error
        setHasAccess(false);
        setData(null);
      })
      .finally(() => setLoading(false));

    return () => controller.abort();
  }, [cnpj]);

  // Render nothing while loading
  if (loading) return null;

  // Render nothing if no access
  if (!hasAccess || !data) return null;

  // Render nothing for suppliers with no contracts
  if (data.concorrente.total_contratos === 0) return null;

  const { concorrente, stats, alertas, territorio, win_metrics, orgaos_favoritos } = data;
  const primaryUF = territorio.length > 0 ? territorio[0] : null;

  return (
    <section
      data-testid="competitive-intel-block"
      className="my-8 rounded-xl border border-gray-200 bg-white p-6 shadow-sm"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-gray-900">
          {"Inteligência Concorrencial"}
        </h2>
        <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-full">
          COMPINT
        </span>
      </div>

      {/* Positioning Alerts */}
      {alertas.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-5">
          {alertas.map((alerta, i) => (
            <div
              key={i}
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm ${ALERT_STYLES[alerta.severidade] || ALERT_STYLES.info}`}
            >
              <span>{ALERT_ICONS[alerta.tipo] || "\u{1F4CA}"}</span>
              <span>{alerta.mensagem}</span>
            </div>
          ))}
        </div>
      )}

      {/* Mini Dashboard */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-5">
        {/* Ticket médio vs mediana */}
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">Ticket Médio</p>
          <p className="text-lg font-bold text-gray-900">
            {fmtBRL(concorrente.ticket_medio)}
          </p>
          <p className="text-xs text-gray-400">
            Mediana: {fmtBRL(concorrente.ticket_mediana)}
          </p>
        </div>

        {/* Market share primary UF */}
        {primaryUF && primaryUF.market_share_uf != null && (
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">Market Share</p>
            <p className="text-lg font-bold text-gray-900">
              {(primaryUF.market_share_uf * 100).toFixed(1)}%
            </p>
            <p className="text-xs text-gray-400">em {primaryUF.uf}</p>
          </div>
        )}

        {/* Crescimento anual */}
        {stats.crescimento_anual != null && (
          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-xs text-gray-500 mb-1">Crescimento Anual</p>
            <p className={`text-lg font-bold ${stats.crescimento_anual >= 0 ? "text-green-600" : "text-red-600"}`}>
              {stats.crescimento_anual >= 0 ? "+" : ""}
              {stats.crescimento_anual.toFixed(0)}%
            </p>
            <p className="text-xs text-gray-400">últimos 12 meses</p>
          </div>
        )}

        {/* UFs de atuação */}
        <div className="bg-gray-50 rounded-lg p-3">
          <p className="text-xs text-gray-500 mb-1">UFs de Atuação</p>
          <p className="text-lg font-bold text-gray-900">{stats.ufs_atuacao}</p>
          <p className="text-xs text-gray-400">
            {territorio.slice(0, 3).map((t) => t.uf).join(", ")}
            {territorio.length > 3 && "..."}
          </p>
        </div>
      </div>

      {/* Win metrics row */}
      {win_metrics && (win_metrics.taxa_vitoria_estimada != null || win_metrics.ticket_p50 != null) && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-5">
          {win_metrics.taxa_vitoria_estimada != null && (
            <div className="bg-indigo-50 rounded-lg p-3">
              <p className="text-xs text-indigo-500 mb-1">Taxa de Vitória Est.</p>
              <p className="text-lg font-bold text-indigo-700">
                {(win_metrics.taxa_vitoria_estimada * 100).toFixed(1)}%
              </p>
            </div>
          )}
          {win_metrics.ticket_p50 != null && (
            <div className="bg-indigo-50 rounded-lg p-3">
              <p className="text-xs text-indigo-500 mb-1">Ticket Mediano (P50)</p>
              <p className="text-lg font-bold text-indigo-700">
                {fmtBRL(win_metrics.ticket_p50)}
              </p>
            </div>
          )}
          {win_metrics.tendencia && (
            <div className="bg-indigo-50 rounded-lg p-3">
              <p className="text-xs text-indigo-500 mb-1">Tendência</p>
              <p className="text-lg font-bold text-indigo-700 capitalize">
                {win_metrics.tendencia === "crescendo" ? "\u{2191} Crescendo" :
                 win_metrics.tendencia === "retraindo" ? "\u{2193} Retraindo" :
                 win_metrics.tendencia === "estavel" ? "\u{2192} Estável" :
                 win_metrics.tendencia}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Favorite agencies snippet */}
      {orgaos_favoritos.length > 0 && (
        <div className="mb-5">
          <p className="text-sm font-medium text-gray-700 mb-2">
            Principais Órgãos Compradores
          </p>
          <div className="flex flex-wrap gap-2">
            {orgaos_favoritos.slice(0, 4).map((orgao, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-gray-100 text-xs text-gray-700"
              >
                <span>{orgao.orgao_nome}</span>
                <span className="text-gray-400">({orgao.contratos} contratos)</span>
              </span>
            ))}
            {orgaos_favoritos.length > 4 && (
              <span className="text-xs text-gray-400 self-center">
                +{orgaos_favoritos.length - 4}
              </span>
            )}
          </div>
        </div>
      )}

      {/* CTA: full dossier */}
      <div className="border-t border-gray-100 pt-4 mt-2">
        <Link
          href={`/intel-concorrente?cnpj=${encodeURIComponent(cnpj)}`}
          className="inline-flex items-center gap-2 text-sm font-medium text-blue-600 hover:text-blue-700 transition-colors"
          data-testid="competitive-intel-cta"
        >
          {"Ver inteligência competitiva completa →"}
        </Link>
      </div>
    </section>
  );
}
