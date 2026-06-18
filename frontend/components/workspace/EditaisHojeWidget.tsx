"use client";

import Link from "next/link";
import { FileText, ExternalLink, Search } from "lucide-react";
import { EmptyState } from "../EmptyState";

interface EditaisHojeItem {
  pncp_id?: string | null;
  orgao?: string | null;
  uf?: string | null;
  objeto?: string | null;
  valor_estimado?: number | null;
  data_publicacao?: string | null;
  data_encerramento?: string | null;
  link_pncp?: string | null;
  modalidade?: string | null;
  numero_compra?: string | null;
}

interface EditaisHojeWidgetProps {
  items: EditaisHojeItem[];
  total: number;
  loading: boolean;
}

/**
 * EditaisHojeWidget — displays up to 10 procurement opportunities published today.
 *
 * B2GOPS-010 (#2020): Widget for the workspace dashboard.
 * Links to /buscar for full search.
 */
export function EditaisHojeWidget({ items, total, loading }: EditaisHojeWidgetProps) {
  return (
    <div className="bg-[var(--surface-0)] rounded-xl border border-[var(--border)] shadow-sm overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)]">
        <div className="flex items-center gap-2">
          <FileText className="w-5 h-5 text-[var(--brand-blue)]" aria-hidden="true" />
          <h2 className="text-base font-semibold text-[var(--ink)]">Editais do Dia</h2>
        </div>
        <span className="text-sm text-[var(--ink-muted)]">{total} hoje</span>
      </div>

      <div className="divide-y divide-[var(--border)]">
        {loading ? (
          <div className="space-y-3 p-5">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-16 bg-[var(--surface-1)] animate-pulse rounded-lg" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="p-5">
            <EmptyState
              title="Nenhum edital hoje"
              description="Nao ha editais publicados hoje no banco de dados. Os dados sao atualizados diariamente."
              icon={<FileText className="w-10 h-10 text-[var(--ink-muted)]" aria-hidden="true" />}
              ctaLabel="Ir para Busca"
              ctaHref="/buscar"
            />
          </div>
        ) : (
          items.map((item, idx) => (
            <div key={item.pncp_id ?? idx} className="px-5 py-3 hover:bg-[var(--surface-1)] transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[var(--ink)] truncate">
                    {item.objeto || "Objeto nao informado"}
                  </p>
                  <p className="text-xs text-[var(--ink-muted)] mt-1">
                    {[item.orgao, item.uf].filter(Boolean).join(" — ")}
                    {item.modalidade ? ` · ${item.modalidade}` : ""}
                    {item.numero_compra ? ` · ${item.numero_compra}` : ""}
                  </p>
                  {item.valor_estimado != null && (
                    <p className="text-xs text-[var(--ink-secondary)] mt-0.5">
                      Valor estimado: R$ {item.valor_estimado.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                    </p>
                  )}
                </div>
                {item.link_pncp && (
                  <a
                    href={item.link_pncp}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 p-1.5 rounded-lg text-[var(--ink-muted)] hover:text-[var(--brand-blue)] hover:bg-[var(--surface-2)] transition-colors"
                    aria-label="Abrir no PNCP"
                  >
                    <ExternalLink className="w-4 h-4" strokeWidth={1.5} />
                  </a>
                )}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="px-5 py-3 border-t border-[var(--border)] bg-[var(--surface-1)]">
        <Link
          href="/buscar"
          className="text-sm font-medium text-[var(--brand-blue)] hover:underline"
        >
          Buscar editais completos &rarr;
        </Link>
      </div>
    </div>
  );
}
