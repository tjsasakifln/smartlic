"use client";

/**
 * REPORT-MONTHLY-001 (#1620): ReportPreview — Displays a sample of the
 * monthly report data for a given sector.
 */

import React from "react";

interface TopOpportunity {
  objeto: string;
  orgao: string;
  valor: number;
  data: string;
}

interface TopWinner {
  nome: string;
  cnpj: string;
  total: number;
  contratos: number;
}

interface ReportPreviewProps {
  sectorId: string;
  sectorName: string;
  period: string;
  totalLicitacoes: number;
  totalValue: number;
  avgValue: number;
  topOpportunities: TopOpportunity[];
  topWinners: TopWinner[];
  executiveSummary: string;
  loading: boolean;
}

export default function ReportPreview({
  sectorId,
  sectorName,
  period,
  totalLicitacoes,
  totalValue,
  avgValue,
  topOpportunities,
  topWinners,
  executiveSummary,
  loading,
}: ReportPreviewProps) {
  if (loading) {
    return (
      <div className="py-12 text-center text-gray-500">
        Carregando preview do relatorio...
      </div>
    );
  }

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("pt-BR", {
      style: "currency",
      currency: "BRL",
    }).format(value);

  return (
    <div className="space-y-8">
      {/* Executive Summary */}
      <section className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          1. Resumo Executivo
        </h2>
        <p className="text-sm leading-relaxed text-gray-700">
          {executiveSummary}
        </p>
      </section>

      {/* Key Metrics */}
      <section className="grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
          <p className="text-2xl font-bold text-green-600">
            {totalLicitacoes}
          </p>
          <p className="mt-1 text-xs text-gray-500">Total de Contratos</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
          <p className="text-2xl font-bold text-green-600">
            {formatCurrency(totalValue)}
          </p>
          <p className="mt-1 text-xs text-gray-500">Valor Total</p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4 text-center">
          <p className="text-2xl font-bold text-green-600">
            {formatCurrency(avgValue)}
          </p>
          <p className="mt-1 text-xs text-gray-500">Valor Medio</p>
        </div>
      </section>

      {/* Top Opportunities */}
      <section className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          2. Top Oportunidades
        </h2>
        {topOpportunities.length === 0 ? (
          <p className="text-sm text-gray-500">
            Nenhuma oportunidade encontrada no periodo.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">
                    #
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">
                    Objeto
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">
                    Orgao
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-gray-500">
                    Valor
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {topOpportunities.map((opp, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-3 py-2 text-gray-400">{i + 1}</td>
                    <td className="max-w-xs truncate px-3 py-2 text-gray-900">
                      {opp.objeto}
                    </td>
                    <td className="max-w-[200px] truncate px-3 py-2 text-gray-600">
                      {opp.orgao}
                    </td>
                    <td className="px-3 py-2 text-right font-medium text-green-700">
                      {formatCurrency(opp.valor)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Top Winners */}
      <section className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          3. Quem Ganhou
        </h2>
        {topWinners.length === 0 ? (
          <p className="text-sm text-gray-500">
            Nenhum vencedor encontrado no periodo.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">
                    #
                  </th>
                  <th className="px-3 py-2 text-left font-medium text-gray-500">
                    Fornecedor
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-gray-500">
                    Total
                  </th>
                  <th className="px-3 py-2 text-right font-medium text-gray-500">
                    Contratos
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {topWinners.map((w, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-3 py-2 text-gray-400">{i + 1}</td>
                    <td className="px-3 py-2 font-medium text-gray-900">
                      {w.nome}
                    </td>
                    <td className="px-3 py-2 text-right text-green-700">
                      {formatCurrency(w.total)}
                    </td>
                    <td className="px-3 py-2 text-right text-gray-600">
                      {w.contratos}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
