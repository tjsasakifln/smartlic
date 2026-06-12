"use client";
/**
 * PREDINT-022 (#1671): IncumbentAlert
 *
 * Lista de fornecedores com sinal de alerta — Bloco 3 do /radar-recorrencia.
 * Exibe fornecedores que estao perdendo espaco em orgaos onde eram
 * predominantes, com CTA para explorar oportunidades de entrada.
 */

import Link from "next/link";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface IncumbentSignal {
  fornecedor: string;
  fornecedor_cnpj: string;
  orgao: string;
  perda_espaco: number; // 0.0 - 1.0
  contratos_perdidos: number;
  valor_em_risco: number;
  motivo: string;
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_ALERTAS: IncumbentSignal[] = [
  {
    fornecedor: "Alimentos SA",
    fornecedor_cnpj: "12345678000190",
    orgao: "Prefeitura Municipal de Sao Paulo",
    perda_espaco: 0.75,
    contratos_perdidos: 4,
    valor_em_risco: 3500000,
    motivo: "Novos concorrentes com precos mais competitivos",
  },
  {
    fornecedor: "Servicos Medicos Ltda",
    fornecedor_cnpj: "98765432000110",
    orgao: "Secretaria de Saude de MG",
    perda_espaco: 0.62,
    contratos_perdidos: 3,
    valor_em_risco: 4200000,
    motivo: "Reducao no numero de contratos renovados",
  },
  {
    fornecedor: "Construcoes RJ Ltda",
    fornecedor_cnpj: "55667788000122",
    orgao: "Governo do Estado do RJ",
    perda_espaco: 0.45,
    contratos_perdidos: 2,
    valor_em_risco: 5800000,
    motivo: "Desempenho insatisfatorio em contratos anteriores",
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function perdaColor(perda: number): string {
  if (perda >= 0.7) return "text-red-600";
  if (perda >= 0.4) return "text-orange-500";
  return "text-yellow-600";
}

function perdaBg(perda: number): string {
  if (perda >= 0.7) return "bg-red-50 border-red-200";
  if (perda >= 0.4) return "bg-orange-50 border-orange-200";
  return "bg-yellow-50 border-yellow-200";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface IncumbentAlertProps {
  alertas?: IncumbentSignal[];
  loading?: boolean;
}

function IncumbentAlert({ alertas, loading = false }: IncumbentAlertProps) {
  const data = alertas ?? MOCK_ALERTAS;

  if (loading) {
    return (
      <div data-testid="incumbent-alert" className="space-y-3 animate-pulse">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="bg-white rounded-lg border p-4">
            <div className="h-4 w-3/4 bg-gray-100 rounded mb-2" />
            <div className="h-3 w-1/2 bg-gray-100 rounded" />
          </div>
        ))}
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div
        data-testid="incumbent-alert"
        className="bg-white rounded-lg border p-6 text-center"
      >
        <p className="text-sm text-gray-500">
          Nenhum alerta de incumbente no momento.
        </p>
      </div>
    );
  }

  return (
    <div data-testid="incumbent-alert" className="space-y-3">
      {data.map((a, i) => (
        <div
          key={`${a.fornecedor_cnpj}-${i}`}
          className={`rounded-lg border p-4 ${perdaBg(a.perda_espaco)}`}
        >
          <div className="flex items-start justify-between mb-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-lg" aria-hidden="true">&#x26A0;&#xFE0F;</span>
                <h4 className="text-sm font-semibold text-gray-900">
                  <Link
                    href={`/fornecedores/${a.fornecedor_cnpj}`}
                    className="hover:underline"
                  >
                    {a.fornecedor}
                  </Link>
                </h4>
              </div>
              <p className="text-xs text-gray-500">
                {a.orgao} &middot; {a.contratos_perdidos} contratos perdidos
              </p>
            </div>
            <span className={`text-sm font-bold whitespace-nowrap ${perdaColor(a.perda_espaco)}`}>
              -{Math.round(a.perda_espaco * 100)}%
            </span>
          </div>

          <p className="text-sm text-gray-600 mb-2">{a.motivo}</p>

          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">
              Valor em risco: {formatBRL(a.valor_em_risco)}
            </span>
            <Link
              href={`/buscar?ref=incumbent-alert-${a.fornecedor_cnpj}`}
              className="text-xs font-semibold text-blue-600 hover:text-blue-700 hover:underline"
            >
              Este fornecedor esta perdendo espaco &mdash; veja onde entrar &rarr;
            </Link>
          </div>
        </div>
      ))}
    </div>
  );
}

export { IncumbentAlert };
export default IncumbentAlert;
