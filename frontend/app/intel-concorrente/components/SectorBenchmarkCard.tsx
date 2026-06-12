'use client';

import { motion } from 'framer-motion';

interface BenchmarkMetric {
  metrica: string;
  label: string;
  valor_concorrente: number;
  percentil_concorrente: number;
  benchmark_setor: {
    p25: number;
    p50: number;
    p75: number;
  };
  descricao: string;
}

interface SectorBenchmarkCardProps {
  metricas: BenchmarkMetric[];
}

function formatCurrency(value: number): string {
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
}

function formatMetricValue(metrica: string, value: number): string {
  if (metrica.includes('ticket') || metrica.includes('valor') || metrica.includes('contratado')) {
    return formatCurrency(value);
  }
  if (metrica.includes('percentil') || metrica.includes('share')) {
    return `${value.toFixed(1)}%`;
  }
  return value.toLocaleString('pt-BR');
}

export default function SectorBenchmarkCard({ metricas }: SectorBenchmarkCardProps) {
  if (!metricas || metricas.length === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg bg-white p-6 shadow-sm"
    >
      <h3 className="mb-4 text-lg font-semibold text-gray-900">
        Benchmark Setorial
      </h3>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {metricas.map((m) => (
          <div
            key={m.metrica}
            className="rounded-lg border border-gray-200 p-4"
          >
            <h4 className="text-sm font-medium text-gray-700">{m.label}</h4>

            {/* Competitor value */}
            <div className="mt-2">
              <span className="text-xs text-gray-500">Concorrente</span>
              <p className="text-lg font-bold text-blue-600">
                {formatMetricValue(m.metrica, m.valor_concorrente)}
              </p>
            </div>

            {/* Percentile badge */}
            <div className="mt-1">
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  m.percentil_concorrente >= 75
                    ? 'bg-green-100 text-green-800'
                    : m.percentil_concorrente >= 50
                      ? 'bg-yellow-100 text-yellow-800'
                      : 'bg-gray-100 text-gray-800'
                }`}
              >
                P{m.percentil_concorrente}
              </span>
            </div>

            {/* Sector benchmark */}
            <div className="mt-3 space-y-1 border-t border-gray-100 pt-2 text-xs text-gray-500">
              <div className="flex justify-between">
                <span>P25 (Setor)</span>
                <span>{formatMetricValue(m.metrica, m.benchmark_setor.p25)}</span>
              </div>
              <div className="flex justify-between font-medium text-gray-700">
                <span>P50 (Mediana)</span>
                <span>{formatMetricValue(m.metrica, m.benchmark_setor.p50)}</span>
              </div>
              <div className="flex justify-between">
                <span>P75 (Setor)</span>
                <span>{formatMetricValue(m.metrica, m.benchmark_setor.p75)}</span>
              </div>
            </div>

            {/* Tooltip */}
            {m.descricao && (
              <p className="mt-2 text-xs text-gray-400 italic">{m.descricao}</p>
            )}
          </div>
        ))}
      </div>
    </motion.div>
  );
}
