"use client";

import Link from "next/link";
import { Search, Columns, BarChart3, ArrowRight } from "lucide-react";

interface QuickAction {
  href: string;
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    href: "/buscar",
    label: "Buscar Editais",
    description: "Pesquise oportunidades por setor, UF e palavras-chave",
    icon: <Search className="w-6 h-6" strokeWidth={1.5} />,
    color: "bg-blue-50 text-blue-600 border-blue-200 hover:bg-blue-100",
  },
  {
    href: "/pipeline",
    label: "Pipeline",
    description: "Gerencie suas oportunidades em andamento",
    icon: <Columns className="w-6 h-6" strokeWidth={1.5} />,
    color: "bg-amber-50 text-amber-600 border-amber-200 hover:bg-amber-100",
  },
  {
    href: "/observatorio",
    label: "Observatorio",
    description: "Acompanhe tendencias e estatisticas do mercado",
    icon: <BarChart3 className="w-6 h-6" strokeWidth={1.5} />,
    color: "bg-green-50 text-green-600 border-green-200 hover:bg-green-100",
  },
];

/**
 * AcoesRapidasWidget — quick-access action cards.
 *
 * B2GOPS-010 (#2020): Shortcuts to /buscar, /pipeline, /observatorio.
 */
export function AcoesRapidasWidget() {
  return (
    <div className="bg-[var(--surface-0)] rounded-xl border border-[var(--border)] shadow-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border)]">
        <h2 className="text-base font-semibold text-[var(--ink)]">Acoes Rapidas</h2>
      </div>

      <div className="p-5 grid grid-cols-1 sm:grid-cols-3 gap-3">
        {QUICK_ACTIONS.map((action) => (
          <Link
            key={action.href}
            href={action.href}
            className={`flex flex-col items-center text-center gap-2 p-4 rounded-xl border transition-colors ${action.color}`}
          >
            <div className="shrink-0">{action.icon}</div>
            <div>
              <p className="font-semibold text-sm">{action.label}</p>
              <p className="text-xs mt-0.5 opacity-80">{action.description}</p>
            </div>
            <ArrowRight className="w-4 h-4 opacity-60" strokeWidth={1.5} />
          </Link>
        ))}
      </div>
    </div>
  );
}
