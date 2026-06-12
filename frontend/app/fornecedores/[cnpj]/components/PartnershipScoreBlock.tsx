"use client";
/**
 * SUBINTEL-011 (#1674): Partnership Score Block
 *
 * Seção aditiva na página /fornecedores/[cnpj] que exibe um Score de
 * Oportunidade de Parceria para o fornecedor consultado.
 *
 * Feature flag: SUBCONTRACT_INTEL_ENABLED
 * Plan capability: allow_subcontract_intel
 *
 * Gating:
 * - Flag desligada (404) → não renderiza nada
 * - Sem capability (403) → CTA de upgrade
 * - OK (200) → gauge + sinais + narrativa
 */

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@/app/components/AuthProvider";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SignalDetail {
  score: number;
  label: string;
  description: string;
  details: Record<string, unknown>;
}

interface CapacitySignals {
  repeat_winner: SignalDetail;
  large_contract: SignalDetail;
  subcontracting_pattern: SignalDetail;
}

interface PartnershipScoreData {
  cnpj: string;
  razao_social: string;
  overall_score: number;
  signals: CapacitySignals;
  narrative: string | null;
  disclaimer: string;
}

type BlockState =
  | { status: "loading" }
  | { status: "hidden" }
  | { status: "upgrade_needed" }
  | { status: "error"; message: string }
  | { status: "ready"; data: PartnershipScoreData };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreColor(score: number): string {
  if (score >= 0.7) return "text-green-600";
  if (score >= 0.4) return "text-yellow-600";
  return "text-red-600";
}

function scoreBg(score: number): string {
  if (score >= 0.7) return "bg-green-500";
  if (score >= 0.4) return "bg-yellow-500";
  return "bg-red-500";
}

function scoreLabel(score: number): string {
  if (score >= 0.7) return "Alto";
  if (score >= 0.4) return "Médio";
  return "Baixo";
}

function ScoreGauge({ score }: { score: number }) {
  const percentage = Math.round(score * 100);
  return (
    <div className="flex items-center gap-3">
      <div className="flex-1 h-4 bg-gray-200 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${scoreBg(score)}`}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
      <span className={`text-2xl font-bold ${scoreColor(score)} min-w-[4rem] text-right`}>
        {scoreLabel(score)}
      </span>
    </div>
  );
}

function SignalBar({ name, signal }: { name: string; signal: SignalDetail }) {
  const percentage = Math.round(signal.score * 100);
  return (
    <div className="mb-3">
      <div className="flex justify-between items-center mb-1">
        <span className="text-sm font-medium text-gray-700">{name}</span>
        <span className={`text-sm font-semibold ${scoreColor(signal.score)}`}>
          {signal.label}
        </span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${scoreBg(signal.score)}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <p className="text-xs text-gray-500 mt-1">{signal.description}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Event tracking
// ---------------------------------------------------------------------------

function trackEvent(eventName: string, properties?: Record<string, unknown>) {
  try {
    if (typeof window !== "undefined" && (window as any).mixpanel) {
      (window as any).mixpanel.track(eventName, properties);
    }
  } catch {
    // Silently fail
  }
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

interface PartnershipScoreBlockProps {
  cnpj: string;
  razaoSocial: string;
}

function PartnershipScoreBlock({ cnpj, razaoSocial }: PartnershipScoreBlockProps) {
  const { user, loading: authLoading } = useAuth();
  const [state, setState] = useState<BlockState>({ status: "loading" });

  const fetchScore = useCallback(async () => {
    setState({ status: "loading" });

    try {
      const resp = await fetch(`/api/v1/subcontract/partnership-score/${cnpj}`, {
        credentials: "include",
        headers: { Accept: "application/json" },
      });

      if (resp.status === 404) {
        // Feature flag off — component is inert
        setState({ status: "hidden" });
        return;
      }

      if (resp.status === 403) {
        // No capability — show upgrade CTA
        setState({ status: "upgrade_needed" });
        trackEvent("subcontract_score_cta_clicked", {
          cnpj,
          reason: "no_capability",
        });
        return;
      }

      if (!resp.ok) {
        setState({
          status: "error",
          message: "Não foi possível carregar o score de parceria.",
        });
        return;
      }

      const data: PartnershipScoreData = await resp.json();
      setState({ status: "ready", data });
      trackEvent("subcontract_score_viewed", {
        cnpj,
        overall_score: data.overall_score,
      });
    } catch (err) {
      setState({
        status: "error",
        message: "Erro de conexão ao carregar score de parceria.",
      });
    }
  }, [cnpj]);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      setState({ status: "hidden" });
      return;
    }
    fetchScore();
  }, [cnpj, user, authLoading, fetchScore]);

  // Hidden states — render nothing
  if (state.status === "hidden" || state.status === "loading" || authLoading) {
    return null;
  }

  // Error state
  if (state.status === "error") {
    return (
      <section
        data-testid="partnership-score-block"
        className="rounded-xl border border-gray-200 bg-gray-50 p-5 my-8"
      >
        <h3 className="text-sm font-semibold text-gray-500 mb-1">
          Score de Oportunidade de Parceria
        </h3>
        <p className="text-sm text-gray-400">
          {state.message}
        </p>
      </section>
    );
  }

  // Upgrade needed
  if (state.status === "upgrade_needed") {
    return (
      <section
        data-testid="partnership-score-block-upgrade"
        className="rounded-xl border border-amber-200 bg-amber-50 p-5 my-8"
      >
        <div className="flex items-start gap-3">
          <span className="text-2xl" aria-hidden="true">&#x1F512;</span>
          <div className="flex-1 min-w-0">
            <h3 className="text-sm font-semibold text-gray-900 mb-1">
              Score de Oportunidade de Parceria
            </h3>
            <p className="text-sm text-gray-600 mb-3">
              Descubra se este fornecedor tem perfil para ser abordado como
              potencial subcontratado ou parceiro. Disponível no plano SmartLic
              Insight.
            </p>
            <a
              href={`/planos?ref=partnership-score-${cnpj}`}
              className="inline-block rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700 transition-colors"
              data-testid="partnership-score-upgrade-cta"
              onClick={() =>
                trackEvent("subcontract_score_cta_clicked", {
                  cnpj,
                  cta: "upgrade_to_insight",
                })
              }
            >
              Ver planos &rarr;
            </a>
          </div>
        </div>
      </section>
    );
  }

  // Ready state
  const { data } = state;
  return (
    <section
      data-testid="partnership-score-block"
      className="rounded-xl border border-gray-200 bg-white p-5 my-8"
    >
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            Score de Oportunidade de Parceria
          </h3>
          <p className="text-sm text-gray-500">
            Potencial de {razaoSocial} como parceiro B2G
          </p>
        </div>
        <div className="text-right">
          <p className="text-xs text-gray-400">Score Geral</p>
          <p className={`text-3xl font-bold ${scoreColor(data.overall_score)}`}>
            {Math.round(data.overall_score * 100)}%
          </p>
        </div>
      </div>

      <ScoreGauge score={data.overall_score} />

      <div className="mt-6 space-y-2">
        <SignalBar name="Vencedor Recorrente" signal={data.signals.repeat_winner} />
        <SignalBar name="Grandes Contratos" signal={data.signals.large_contract} />
        <SignalBar
          name="Padrão de Subcontratação"
          signal={data.signals.subcontracting_pattern}
        />
      </div>

      {data.narrative && (
        <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm text-gray-700">
          {data.narrative}
        </div>
      )}

      <p className="mt-4 text-xs text-gray-400">{data.disclaimer}</p>
    </section>
  );
}

export { PartnershipScoreBlock };
export default PartnershipScoreBlock;
