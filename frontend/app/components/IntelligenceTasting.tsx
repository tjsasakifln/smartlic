"use client";

/**
 * DEGUST-001 (#1611): Intelligence Tasting component.
 *
 * Shows aggregated market intelligence from pncp_supplier_contracts.
 * - Free/trial users: real data with blurred winner names + CTA
 * - Paid users: full data without blur
 *
 * Inserted post-search and in dashboard.
 */

import { useEffect, useState } from "react";
import mixpanel from "mixpanel-browser";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TastingWinner {
  cnpj: string;
  razao_social: string;
  total_won: number;
  contracts_count: number;
}

interface TastingData {
  sector_id: string;
  sector_name: string;
  uf?: string | null;
  period_months: number;
  total_contracts_value: number;
  total_winners: number;
  total_contracts: number;
  avg_contract_value: number;
  top_winners: TastingWinner[];
  generated_at: string;
  feature_enabled: boolean;
}

interface IntelligenceTastingProps {
  /** Sector ID from the search context, if available */
  sectorId?: string;
  /** UF from the search context, if available */
  uf?: string;
  /** Whether the user has a paid plan (Insight/Pro/Command) */
  isPaidUser?: boolean;
  /** CTA URL for upgrade */
  upgradeUrl?: string;
}

// ---------------------------------------------------------------------------
// Formatting helpers
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

function fmtInt(n: number): string {
  return n.toLocaleString("pt-BR");
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function IntelligenceTasting({
  sectorId,
  uf,
  isPaidUser = false,
  upgradeUrl = "/pricing?tier=insight",
}: IntelligenceTastingProps) {
  const [data, setData] = useState<TastingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchTasting() {
      try {
        setLoading(true);
        const params = new URLSearchParams();
        if (sectorId) params.set("setor_id", sectorId);
        if (uf) params.set("uf", uf);
        params.set("meses", "12");

        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL}/v1/intel/tasting?${params}`
        );
        if (!res.ok) {
          if (res.status === 404) {
            // Feature disabled or not found — silent
            setData(null);
            return;
          }
          throw new Error(`HTTP ${res.status}`);
        }
        const json: TastingData = await res.json();
        if (!cancelled) {
          setData(json);
          // Track shown event
          try {
            mixpanel.track("intelligence_tasting_shown", {
              sector_id: json.sector_id,
              total_winners: json.total_winners,
              total_value: json.total_contracts_value,
              is_paid_user: isPaidUser,
              uf: uf || "BR",
            });
          } catch {
            // Mixpanel may not be initialized (consent)
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Erro ao carregar");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchTasting();
    return () => {
      cancelled = true;
    };
  }, [sectorId, uf, isPaidUser]);

  function handleCtaClick() {
    try {
      mixpanel.track("intelligence_tasting_clicked", {
        sector_id: data?.sector_id || "unknown",
        is_paid_user: isPaidUser,
      });
    } catch {
      // Mixpanel may not be initialized
    }
  }

  // ------------------------------------------------------------------
  // States: loading / error / disabled / empty / content
  // ------------------------------------------------------------------

  if (loading) {
    return (
      <div className="animate-pulse rounded-xl border border-slate-200 bg-white p-6">
        <div className="mb-4 h-5 w-3/4 rounded bg-slate-200" />
        <div className="grid grid-cols-3 gap-4">
          <div className="h-16 rounded bg-slate-100" />
          <div className="h-16 rounded bg-slate-100" />
          <div className="h-16 rounded bg-slate-100" />
        </div>
        <div className="mt-4 space-y-2">
          <div className="h-10 rounded bg-slate-100" />
          <div className="h-10 rounded bg-slate-100" />
          <div className="h-10 rounded bg-slate-100" />
        </div>
      </div>
    );
  }

  if (error || !data) {
    // Graceful degradation — don't show error to user
    return null;
  }

  if (!data.feature_enabled || data.total_winners === 0) {
    return null; // No data or feature disabled
  }

  const showBlur = !isPaidUser;

  return (
    <div className="rounded-xl border border-blue-100 bg-gradient-to-br from-blue-50 to-white p-6 shadow-sm">
      {/* Header */}
      <div className="mb-5 flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">
            Inteligência de Mercado
            {data.sector_id !== "global" && (
              <span className="font-normal text-slate-500">
                {" "}
                — {data.sector_name}
              </span>
            )}
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Dados reais dos últimos {data.period_months} meses
            {data.uf ? ` em ${data.uf}` : " no Brasil"}
          </p>
        </div>
        {showBlur && (
          <span className="shrink-0 rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-700">
            🔒 Preview
          </span>
        )}
      </div>

      {/* Stats grid */}
      <div className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg bg-white p-3 shadow-sm ring-1 ring-slate-200/60">
          <div className="text-2xl font-bold text-blue-700">
            {fmtBRL(data.total_contracts_value)}
          </div>
          <div className="text-xs text-slate-500">Valor total contratado</div>
        </div>
        <div className="rounded-lg bg-white p-3 shadow-sm ring-1 ring-slate-200/60">
          <div className="text-2xl font-bold text-blue-700">
            {fmtInt(data.total_winners)}
          </div>
          <div className="text-xs text-slate-500">Empresas vencedoras</div>
        </div>
        <div className="rounded-lg bg-white p-3 shadow-sm ring-1 ring-slate-200/60">
          <div className="text-2xl font-bold text-blue-700">
            {fmtInt(data.total_contracts)}
          </div>
          <div className="text-xs text-slate-500">Contratos fechados</div>
        </div>
        <div className="rounded-lg bg-white p-3 shadow-sm ring-1 ring-slate-200/60">
          <div className="text-2xl font-bold text-blue-700">
            {fmtBRL(data.avg_contract_value)}
          </div>
          <div className="text-xs text-slate-500">Valor médio por contrato</div>
        </div>
      </div>

      {/* Top Winners */}
      <div className="mb-4">
        <h4 className="mb-2 text-sm font-semibold text-slate-700">
          Top {data.top_winners.length} vencedores
          {showBlur && (
            <span className="ml-2 font-normal text-slate-400">
              (nomes ocultos)
            </span>
          )}
        </h4>
        <div className="space-y-2">
          {data.top_winners.map((winner, i) => (
            <div
              key={winner.cnpj || i}
              className="flex items-center justify-between rounded-lg bg-white px-4 py-2.5 shadow-sm ring-1 ring-slate-200/60"
            >
              <div className="flex items-center gap-3">
                <span className="text-xs font-medium text-slate-400">
                  #{i + 1}
                </span>
                <span
                  className={
                    showBlur
                      ? "select-none rounded bg-slate-200 px-3 py-1 text-sm text-transparent blur-[4px]"
                      : "text-sm font-medium text-slate-800"
                  }
                >
                  {winner.razao_social}
                </span>
                {showBlur && (
                  <span className="text-xs text-slate-400">██████</span>
                )}
              </div>
              <div className="text-right">
                <div className="text-sm font-semibold text-slate-700">
                  {fmtBRL(winner.total_won)}
                </div>
                <div className="text-xs text-slate-400">
                  {winner.contracts_count} contrato
                  {winner.contracts_count !== 1 ? "s" : ""}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* CTA for non-paid users */}
      {showBlur && (
        <div className="rounded-lg bg-blue-600 p-4 text-center">
          <p className="mb-2 text-sm font-medium text-blue-100">
            🔓 Veja os nomes reais e acesse análises completas de inteligência
            competitiva
          </p>
          <a
            href={upgradeUrl}
            onClick={handleCtaClick}
            className="inline-block rounded-lg bg-white px-6 py-2.5 text-sm font-semibold text-blue-700 shadow transition hover:bg-blue-50"
          >
            Fazer upgrade para SmartLic Insight — R$497/mês
          </a>
          <p className="mt-1 text-xs text-blue-200">
            Dados reais do PNCP processados pelo SmartLic
          </p>
        </div>
      )}

      {/* Footer */}
      <div className="mt-3 text-center text-xs text-slate-400">
        Dados: PNCP — Portal Nacional de Contratações Públicas · Atualizado{" "}
        {new Date(data.generated_at).toLocaleDateString("pt-BR")}
      </div>
    </div>
  );
}
