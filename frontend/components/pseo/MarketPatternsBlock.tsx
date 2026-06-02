"use client";
/**
 * MarketPatternsBlock — Issue #1288 (NETINT-011)
 *
 * Bloco aditivo "Padrões de Mercado" para páginas de setor do pSEO.
 * Exibe inteligência agregada de mercado para cada setor:
 *   (a) média de licitações/mês
 *   (b) valor médio dos contratos
 *   (c) principais órgãos compradores
 *   (d) sazonalidade (meses com mais publicações)
 *
 * Loading skeleton, empty state ("Dados de mercado em consolidação"),
 * e error state (graceful degradation — oculta bloco).
 */

import { useEffect, useState } from "react";

export interface MarketPatternsBlockProps {
  setor: string; // URL slug, e.g. "engenharia"
}

/** Data shape returned by /api/pseo/market-patterns */
export interface MarketPatternsData {
  setor: string;
  setor_nome: string;
  media_licitacoes_mes: number;
  valor_medio_contratos: number;
  top_orgaos: {
    nome: string;
    total_contratos: number;
    valor_total: number;
  }[];
  sazonalidade: {
    mes: string;
    total_publicacoes: number;
  }[];
  total_empresas_entrantes: number;
  tendencia_desconto: {
    desconto_medio_pct: number;
    variacao_anual_pct: number;
  };
  last_updated: string;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCompactBRL(value: number): string {
  if (value >= 1_000_000_000) {
    return `R$${(value / 1_000_000_000).toLocaleString("pt-BR", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })} bi`;
  }
  if (value >= 1_000_000) {
    return `R$${(value / 1_000_000).toLocaleString("pt-BR", {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })} mi`;
  }
  if (value >= 1_000) {
    return `R$${(value / 1_000).toLocaleString("pt-BR", {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    })} mil`;
  }
  return value.toLocaleString("pt-BR", {
    style: "currency",
    currency: "BRL",
  });
}

function formatNumber(value: number): string {
  return value.toLocaleString("pt-BR");
}

/** InfoIcon — subtle info circle SVG for empty state */
function InfoIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function SkeletonCard() {
  return (
    <div className="p-5 rounded-xl border border-[var(--border)] animate-pulse">
      <div className="h-4 bg-[var(--surface-2)] rounded w-2/3 mb-3" />
      <div className="h-8 bg-[var(--surface-2)] rounded w-1/2 mb-2" />
      <div className="h-3 bg-[var(--surface-2)] rounded w-1/3" />
    </div>
  );
}

function SkeletonList() {
  return (
    <div className="p-5 rounded-xl border border-[var(--border)] animate-pulse">
      <div className="h-4 bg-[var(--surface-2)] rounded w-2/3 mb-4" />
      {[1, 2, 3].map((i) => (
        <div key={i} className="flex items-center gap-2 mb-2">
          <div className="h-3 bg-[var(--surface-2)] rounded flex-1" />
          <div className="h-3 bg-[var(--surface-2)] rounded w-12" />
        </div>
      ))}
    </div>
  );
}

function MarketPatternsSkeleton() {
  return (
    <section aria-label="Padrões de Mercado" className="max-w-5xl mx-auto py-10 px-4">
      <div className="h-5 bg-[var(--surface-2)] rounded w-48 mb-6 animate-pulse" />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonList />
        <SkeletonList />
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export function MarketPatternsBlock({ setor }: MarketPatternsBlockProps) {
  const [data, setData] = useState<MarketPatternsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);

    fetch(`/api/pseo/market-patterns?setor=${encodeURIComponent(setor)}`)
      .then((res) => {
        if (!res.ok) throw new Error("API error");
        return res.json();
      })
      .then((json: MarketPatternsData) => {
        if (!cancelled) {
          setData(json);
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError(true);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [setor]);

  // Error state: hide block entirely (graceful degradation)
  if (error) {
    return null;
  }

  // Loading state
  if (loading) {
    return <MarketPatternsSkeleton />;
  }

  // Empty state: show gentle consolidation message
  if (!data) {
    return null;
  }

  // Verify we have meaningful data
  const hasMeaningfulData =
    data.media_licitacoes_mes > 0 ||
    data.valor_medio_contratos > 0 ||
    data.top_orgaos.length > 0 ||
    data.sazonalidade.length > 0;

  if (!hasMeaningfulData) {
    return (
      <section
        aria-label="Padrões de Mercado"
        className="max-w-5xl mx-auto py-8 px-4"
      >
        <div className="flex items-center gap-3 p-5 rounded-xl border border-[var(--border)] bg-[var(--surface-1)]">
          <InfoIcon className="w-5 h-5 text-[var(--ink-muted)] shrink-0" />
          <div>
            <h3 className="text-sm font-semibold text-[var(--ink)]">
              Padrões de Mercado
            </h3>
            <p className="text-sm text-[var(--ink-secondary)] mt-0.5">
              Dados de mercado em consolidação. Volte em breve para
              estatísticas agregadas deste setor.
            </p>
          </div>
        </div>
      </section>
    );
  }

  // Data state
  const topOrgaos = data.top_orgaos.slice(0, 4);
  const sazonalidade = data.sazonalidade.slice(0, 6);
  const maxSaz = Math.max(...sazonalidade.map((s) => s.total_publicacoes), 1);

  return (
    <section
      aria-label="Padrões de Mercado"
      className="max-w-5xl mx-auto py-10 px-4"
    >
      <h2 className="text-xl font-bold text-[var(--ink)] mb-1">
        Padrões de Mercado
      </h2>
      <p className="text-sm text-[var(--ink-secondary)] mb-6">
        Inteligência agregada para {data.setor_nome}
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {/* (a) Média de licitações/mês */}
        <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--surface-0)]">
          <p className="text-sm text-[var(--ink-secondary)] mb-1">
            Média de licitações/mês
          </p>
          <p className="text-2xl font-bold text-[var(--ink)]">
            {formatNumber(data.media_licitacoes_mes)}
          </p>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            Últimos 12 meses
          </p>
        </div>

        {/* (b) Valor médio dos contratos */}
        <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--surface-0)]">
          <p className="text-sm text-[var(--ink-secondary)] mb-1">
            Valor médio dos contratos
          </p>
          <p className="text-2xl font-bold text-[var(--ink)]">
            {formatCompactBRL(data.valor_medio_contratos)}
          </p>
          <p className="text-xs text-[var(--ink-muted)] mt-1">
            Média por contrato
          </p>
        </div>

        {/* (c) Principais órgãos compradores */}
        <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--surface-0)]">
          <p className="text-sm text-[var(--ink-secondary)] mb-3">
            Principais órgãos compradores
          </p>
          <div className="space-y-2">
            {topOrgaos.map((orgao) => (
              <div
                key={orgao.nome}
                className="flex items-center justify-between"
              >
                <span className="text-sm text-[var(--ink)] truncate pr-2 max-w-[60%]">
                  {orgao.nome}
                </span>
                <span className="text-xs text-[var(--ink-secondary)] whitespace-nowrap">
                  {formatNumber(orgao.total_contratos)} contratos
                </span>
              </div>
            ))}
          </div>
          <p className="text-xs text-[var(--ink-muted)] mt-3">
            Ranking por volume de contratos
          </p>
        </div>

        {/* (d) Sazonalidade */}
        <div className="p-5 rounded-xl border border-[var(--border)] bg-[var(--surface-0)]">
          <p className="text-sm text-[var(--ink-secondary)] mb-3">
            Sazonalidade (últimos 6 meses)
          </p>
          <div className="space-y-2">
            {sazonalidade.map((s) => (
              <div key={s.mes} className="flex items-center gap-2">
                <span className="text-xs text-[var(--ink-secondary)] w-8 shrink-0">
                  {s.mes}
                </span>
                <div className="flex-1 bg-[var(--surface-1)] rounded-full h-2.5 overflow-hidden">
                  <div
                    className="h-full bg-[var(--brand-blue)]/60 rounded-full transition-all"
                    style={{
                      width: `${Math.max(4, (s.total_publicacoes / maxSaz) * 100)}%`,
                    }}
                  />
                </div>
                <span className="text-xs text-[var(--ink-secondary)] w-10 text-right">
                  {formatNumber(s.total_publicacoes)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="text-xs text-[var(--ink-muted)] mt-4 text-center">
        Dados agregados de fontes públicas (PNCP) —{" "}
        {new Date(data.last_updated).toLocaleDateString("pt-BR")}
      </p>
    </section>
  );
}
