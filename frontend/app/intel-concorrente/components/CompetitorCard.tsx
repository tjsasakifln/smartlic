'use client';

import { motion } from 'framer-motion';

interface CompetitorCardProps {
  razao_social: string;
  cnpj: string;
  total_contratado: number;
  total_contratos: number;
  ufs_count: number;
  tendencia: string;
}

function formatCurrency(value: number): string {
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
}

const TREND_CONFIG: Record<string, { label: string; color: string }> = {
  crescimento: { label: 'Em expansao', color: 'text-green-600 bg-green-50' },
  estavel: { label: 'Estavel', color: 'text-yellow-600 bg-yellow-50' },
  retracao: { label: 'Em retracao', color: 'text-red-600 bg-red-50' },
};

export default function CompetitorCard({
  razao_social,
  cnpj,
  total_contratado,
  total_contratos,
  ufs_count,
  tendencia,
}: CompetitorCardProps) {
  const trend = TREND_CONFIG[tendencia] || TREND_CONFIG.estavel;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="rounded-lg bg-white p-6 shadow-sm"
    >
      <h3 className="text-lg font-semibold text-gray-900">
        {razao_social}
      </h3>
      <p className="mt-1 text-sm text-gray-500">CNPJ: {cnpj}</p>

      <div className="mt-4 space-y-3">
        <div className="flex items-center justify-between border-b border-gray-100 pb-2">
          <span className="text-sm text-gray-600">Total Contratado</span>
          <span className="text-sm font-semibold text-gray-900">
            {formatCurrency(total_contratado)}
          </span>
        </div>
        <div className="flex items-center justify-between border-b border-gray-100 pb-2">
          <span className="text-sm text-gray-600">Total de Contratos</span>
          <span className="text-sm font-semibold text-gray-900">
            {total_contratos}
          </span>
        </div>
        <div className="flex items-center justify-between border-b border-gray-100 pb-2">
          <span className="text-sm text-gray-600">UFs de Atuacao</span>
          <span className="text-sm font-semibold text-gray-900">
            {ufs_count}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-sm text-gray-600">Tendencia</span>
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${trend.color}`}
          >
            {trend.label}
          </span>
        </div>
      </div>
    </motion.div>
  );
}
