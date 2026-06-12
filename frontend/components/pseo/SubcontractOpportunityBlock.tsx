"use client";

/**
 * SubcontractOpportunityBlock — SUBINTEL-022 (#1678)
 *
 * Aditive block for pSEO pages (open bid pages) that identifies potential
 * subcontracting opportunities for that specific bid.
 *
 * - Lazy-load via IntersectionObserver
 * - ISR-safe: static fallback if API fails
 * - Gate-closed: shows CTA upsell
 *
 * Usage:
 *   <SubcontractOpportunityBlock bidId="pncp-id-123" sector="engenharia" />
 */
import { useEffect, useRef, useState } from "react";
import mixpanel from "mixpanel-browser";

export interface SubcontractOpportunityBlockProps {
  bidId: string;
  sector?: string;
  isPremiumUser?: boolean;
  upgradeUrl?: string;
}

interface ReasonItem {
  reason: string;
  weight: number;
}

interface HistoricalSupplier {
  cnpj: string;
  razao_social?: string | null;
  similar_contracts_count: number;
  total_value: number;
  avg_value: number;
  last_contract_year?: number | null;
  match_reason: string;
}

interface OpportunityData {
  bid_id: string;
  bid_value: number;
  bid_sector: string;
  subcontract_potential_score: number;
  reasons: ReasonItem[];
  historical_suppliers: HistoricalSupplier[];
  disclaimer: string;
  generated_at: string;
}

function fmtBRL(value: number): string {
  if (value >= 1_000_000_000) return `R$ ${(value / 1_000_000_000).toFixed(1).replace(".", ",")} bi`;
  if (value >= 1_000_000) return `R$ ${(value / 1_000_000).toFixed(1).replace(".", ",")} mi`;
  return `R$ ${value.toLocaleString("pt-BR")}`;
}

function getScoreColor(score: number): string {
  if (score >= 0.7) return "text-green-600";
  if (score >= 0.4) return "text-yellow-600";
  return "text-gray-500";
}

function getScoreBg(score: number): string {
  if (score >= 0.7) return "bg-green-100";
  if (score >= 0.4) return "bg-yellow-100";
  return "bg-gray-100";
}

function staticFallback(bidId: string): OpportunityData {
  return {
    bid_id: bidId,
    bid_value: 0,
    bid_sector: "geral",
    subcontract_potential_score: 0,
    reasons: [],
    historical_suppliers: [],
    disclaimer: "Dados indisponiveis no momento. Tente novamente mais tarde.",
    generated_at: new Date().toISOString(),
  };
}

export function SubcontractOpportunityBlock({
  bidId,
  sector,
  isPremiumUser = false,
  upgradeUrl = "/planos",
}: SubcontractOpportunityBlockProps) {
  const [data, setData] = useState<OpportunityData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [gateClosed, setGateClosed] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !data && !loading) fetchData();
        }
      },
      { rootMargin: "200px" }
    );

    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bidId, sector]);

  async function fetchData() {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams({ bid: bidId });
      if (sector) params.set("sector", sector);

      const res = await fetch(`/api/subcontract/opportunities?${params}`);
      if (res.status === 404 || res.status === 403) {
        setGateClosed(true);
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const json: OpportunityData = await res.json();
      setData(json);
      mixpanel.track("subcontract_bid_potential_viewed", { bid_id: bidId, sector: sector || "none", score: json.subcontract_potential_score });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao carregar");
      setData(staticFallback(bidId));
    } finally {
      setLoading(false);
    }
  }

  function handleCta() {
    mixpanel.track("subcontract_bid_potential_cta", { bid_id: bidId, sector: sector || "none" });
    window.location.href = upgradeUrl;
  }

  return (
    <div ref={ref} className="rounded-lg border border-gray-200 bg-white p-4 sm:p-6" data-subcontract-opportunity-block>
      {loading && !data && (
        <div className="animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-3"></div>
          <div className="h-3 bg-gray-200 rounded w-2/3 mb-2"></div>
          <div className="h-3 bg-gray-200 rounded w-1/2 mb-4"></div>
          <div className="space-y-2">
            {[1, 2, 3].map((i) => <div key={i} className="h-8 bg-gray-200 rounded"></div>)}
          </div>
        </div>
      )}

      {gateClosed && !data && (
        <div className="text-center py-4">
          <h3 className="text-base font-semibold text-gray-800 mb-2">Potencial de Subcontratacao</h3>
          <p className="text-sm text-gray-600 mb-3">Identifique fornecedores com perfil para subcontratar este edital.</p>
          <button onClick={handleCta} className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
            SmartLic Insight — Desbloquear
          </button>
        </div>
      )}

      {data && !gateClosed && (
        <>
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-base font-semibold text-gray-800">Potencial de Subcontratacao</h3>
            <span className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-bold ${getScoreBg(data.subcontract_potential_score)} ${getScoreColor(data.subcontract_potential_score)}`}>
              {(data.subcontract_potential_score * 100).toFixed(0)}%
            </span>
          </div>

          {data.bid_value > 0 && (
            <p className="text-sm text-gray-500 mb-3">Edital de <strong>{fmtBRL(data.bid_value)}</strong> no setor <strong>{data.bid_sector}</strong></p>
          )}

          <div className="mb-4">
            <div className="h-2 rounded-full bg-gray-200">
              <div className="h-2 rounded-full transition-all duration-500" style={{
                width: `${Math.min(data.subcontract_potential_score * 100, 100)}%`,
                backgroundColor: data.subcontract_potential_score >= 0.7 ? "#16a34a" : data.subcontract_potential_score >= 0.4 ? "#ca8a04" : "#6b7280",
              }} />
            </div>
          </div>

          {data.reasons.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Fatores considerados</h4>
              <ul className="space-y-1">
                {data.reasons.map((r, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
                    <span className="mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full bg-blue-400" />
                    {r.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {data.historical_suppliers.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Fornecedores historicos com perfil</h4>
              <div className="space-y-2">
                {data.historical_suppliers.slice(0, 5).map((s, i) => (
                  <div key={i} className="rounded border border-gray-100 bg-gray-50 p-2 text-sm">
                    <p className="font-medium text-gray-800">{s.razao_social || s.cnpj}</p>
                    <p className="text-xs text-gray-500">
                      {s.similar_contracts_count} contratos similares · {fmtBRL(s.total_value)} em contratos · Media {fmtBRL(s.avg_value)}
                      {s.last_contract_year ? ` · Ultimo: ${s.last_contract_year}` : ""}
                    </p>
                    <p className="text-xs text-blue-600 mt-0.5">{s.match_reason}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <p className="text-xs text-gray-400 italic mt-3">{data.disclaimer}</p>
        </>
      )}

      {error && !data && <p className="text-sm text-gray-400 text-center py-3">Dados temporariamente indisponiveis.</p>}
    </div>
  );
}
