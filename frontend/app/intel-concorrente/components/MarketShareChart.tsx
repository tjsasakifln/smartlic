'use client';

import React from 'react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

interface CompetitorItem {
  razao_social: string;
  market_share: number;
  total_contratado: number;
}

interface MarketShareChartProps {
  competitors: CompetitorItem[];
}

const COLORS = [
  '#3B82F6',
  '#10B981',
  '#F59E0B',
  '#EF4444',
  '#8B5CF6',
  '#EC4899',
  '#14B8A6',
  '#F97316',
  '#6366F1',
  '#84CC16',
];

function formatCurrency(value: number): string {
  return value.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  });
}

export default function MarketShareChart({ competitors }: MarketShareChartProps) {
  if (!competitors || competitors.length === 0) {
    return (
      <div className="rounded-lg bg-white p-6 shadow-sm">
        <h3 className="mb-4 text-lg font-semibold text-gray-900">
          Market Share por Concorrente
        </h3>
        <p className="text-sm text-gray-500">
          Selecione um setor e clique em &quot;Carregar Panorama&quot; para visualizar o grafico.
        </p>
      </div>
    );
  }

  // Take top 10 for the chart
  const chartData = competitors.slice(0, 10).map((c) => ({
    name:
      c.razao_social.length > 20
        ? `${c.razao_social.slice(0, 18)}...`
        : c.razao_social,
    share: c.market_share,
    fullName: c.razao_social,
    value: c.total_contratado,
  }));

  return (
    <div className="rounded-lg bg-white p-6 shadow-sm">
      <h3 className="mb-4 text-lg font-semibold text-gray-900">
        Market Share por Concorrente
      </h3>

      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={chartData}
          layout="vertical"
          margin={{ top: 5, right: 30, left: 100, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
          <XAxis
            type="number"
            tick={{ fontSize: 12 }}
            domain={[0, 'dataMax + 10']}
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 11 }}
            width={100}
          />
          <Tooltip
            formatter={(value, _name) => {
              const v = value as number | string | undefined;
              return [`${typeof v === 'number' ? v.toFixed(1) : v}%`, 'Market Share'];
            }}
            labelFormatter={(label) => {
              const labelStr = typeof label === 'string' ? label : String(label ?? '');
              const item = chartData.find((d) => d.name === labelStr);
              return `${item?.fullName || labelStr}\n${item?.value ? formatCurrency(item.value) : ''}`;
            }}
          />
          <Bar dataKey="share" radius={[0, 4, 4, 0]}>
            {chartData.map((_entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={COLORS[index % COLORS.length]}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
