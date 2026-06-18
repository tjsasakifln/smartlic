"use client";

import Link from "next/link";
import { ListTodo, ArrowRight } from "lucide-react";
import { EmptyState } from "../EmptyState";

interface PipelineItem {
  id: string;
  stage: string;
  objeto?: string | null;
  orgao?: string | null;
  data_encerramento?: string | null;
  valor_estimado?: number | null;
  is_expired?: boolean;
}

interface PipelineRapidoWidgetProps {
  items: PipelineItem[];
  total: number;
  loading: boolean;
}

const STAGE_LABELS: Record<string, string> = {
  descoberta: "Descoberta",
  analise: "Analise",
  preparando: "Preparando",
  enviada: "Enviada",
  resultado: "Resultado",
};

const STAGE_COLORS: Record<string, string> = {
  descoberta: "text-blue-500",
  analise: "text-amber-500",
  preparando: "text-purple-500",
  enviada: "text-green-500",
  resultado: "text-gray-500",
};

function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("pt-BR");
  } catch {
    return "";
  }
}

/**
 * PipelineRapidoWidget — displays top 5 pipeline items.
 *
 * B2GOPS-010 (#2020): Quick-access widget for the workspace dashboard.
 * Links to /pipeline for full view.
 */
export function PipelineRapidoWidget({ items, total, loading }: PipelineRapidoWidgetProps) {
  return (
    <div className="bg-[var(--surface-0)] rounded-xl border border-[var(--border)] shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <ListTodo className="w-5 h-5 text-[var(--brand-blue)]" aria-hidden="true" />
          <h2 className="text-base font-semibold text-[var(--ink)]">Pipeline Rapido</h2>
        </div>
        <span className="text-sm text-[var(--ink-muted)]">{total} itens</span>
      </div>

      <div className="divide-y divide-[var(--border)]">
        {loading ? (
          <div className="space-y-3 p-5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-14 bg-[var(--surface-1)] animate-pulse rounded-lg" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="Pipeline vazio"
              description="Adicione oportunidades ao seu pipeline durante a busca."
              icon={<ListTodo className="w-10 h-10 text-[var(--ink-muted)]" aria-hidden="true" />}
              ctaLabel="Buscar Editais"
              ctaHref="/buscar"
            />
          </div>
        ) : (
          items.map((item) => (
            <Link
              key={item.id}
              href="/pipeline"
              className="block px-5 py-3 hover:bg-[var(--surface-1)] transition-colors"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[var(--ink)] truncate">
                    {item.objeto || "Objeto nao informado"}
                  </p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`text-xs font-medium ${STAGE_COLORS[item.stage] ?? "text-gray-400"}`}>
                      {STAGE_LABELS[item.stage] ?? item.stage}
                    </span>
                    {item.orgao && (
                      <span className="text-xs text-[var(--ink-muted)]">{item.orgao}</span>
                    )}
                  </div>
                </div>
                <div className="text-right shrink-0">
                  {item.valor_estimado != null && (
                    <p className="text-xs font-medium text-[var(--ink)]">
                      R$ {item.valor_estimado.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                  )}
                  {item.data_encerramento && (
                    <p className={`text-xs mt-0.5 ${item.is_expired ? "text-red-500" : "text-[var(--ink-muted)]"}`}>
                      {item.is_expired ? "Vencido" : `Ate ${formatDate(item.data_encerramento)}`}
                    </p>
                  )}
                </div>
              </div>
            </Link>
          ))
        )}
      </div>

      <div className="px-5 py-3 border-t border-[var(--border)] bg-[var(--surface-1)]">
        <Link
          href="/pipeline"
          className="text-sm font-medium text-[var(--brand-blue)] hover:underline flex items-center gap-1"
        >
          Ver pipeline completo
          <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
        </Link>
      </div>
    </div>
  );
}
