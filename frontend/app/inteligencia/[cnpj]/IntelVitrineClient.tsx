/**
 * VITRINE-001 (#1612): Client component for vitrine charts.
 *
 * Renders Recharts charts for UF distribution, yearly trends, and modality
 * distribution. Marked as 'use client' because Recharts requires browser APIs.
 */

'use client';

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from 'recharts';
import type { IntelVitrineData } from './page';

interface Props {
  vitrine: IntelVitrineData;
  formatBRL: (value: number) => string;
}

const UF_COLORS = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16',
];

const MODALIDADE_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899'];

export default function IntelVitrineClient({ vitrine, formatBRL }: Props) {
  const hasUfData = vitrine.distribuicao_uf.length > 0;
  const hasAnoData = vitrine.distribuicao_ano.length > 0;
  const hasModalidadeData = vitrine.distribuicao_modalidade.length > 0;
  const hasCharts = hasUfData || hasAnoData || hasModalidadeData;

  if (!hasCharts) return null;

  return (
    <section className="mb-10">
      <h2 className="text-xl font-semibold text-ink mb-6">
        Distribuição de Contratos
      </h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* UF Distribution — Bar Chart */}
        {hasUfData && (
          <div className="bg-surface-1 border border-[var(--border)] rounded-xl p-4 sm:p-6">
            <h3 className="text-sm font-semibold text-ink mb-4">
              Contratos por UF
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={vitrine.distribuicao_uf.slice(0, 10)}
                  margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="chave"
                    tick={{ fontSize: 11 }}
                    axisLine={{ stroke: '#e5e7eb' }}
                  />
                  <YAxis tick={{ fontSize: 11 }} axisLine={false} />
                  <Tooltip
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    formatter={(value: any) => formatBRL(Number(value)) as any}
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    labelFormatter={(label: any) => `UF: ${String(label)}`}
                  />
                  <Bar
                    dataKey="valor_total"
                    fill="#3b82f6"
                    radius={[4, 4, 0, 0]}
                    name="Valor Total"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Year Distribution — Line Chart */}
        {hasAnoData && (
          <div className="bg-surface-1 border border-[var(--border)] rounded-xl p-4 sm:p-6">
            <h3 className="text-sm font-semibold text-ink mb-4">
              Evolução por Ano
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={[...vitrine.distribuicao_ano].reverse()}
                  margin={{ top: 5, right: 10, left: 10, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis
                    dataKey="chave"
                    tick={{ fontSize: 11 }}
                    axisLine={{ stroke: '#e5e7eb' }}
                  />
                  <YAxis tick={{ fontSize: 11 }} axisLine={false} />
                  <Tooltip
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    formatter={(value: any) => formatBRL(Number(value)) as any}
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    labelFormatter={(label: any) => `Ano: ${String(label)}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="valor_total"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ r: 4, fill: '#10b981' }}
                    name="Valor Total"
                  />
                  <Line
                    type="monotone"
                    dataKey="quantidade"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 4, fill: '#3b82f6' }}
                    name="Quantidade"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Modalidade Distribution — Pie Chart */}
        {hasModalidadeData && (
          <div className="bg-surface-1 border border-[var(--border)] rounded-xl p-4 sm:p-6">
            <h3 className="text-sm font-semibold text-ink mb-4">
              Distribuição por Modalidade
            </h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={vitrine.distribuicao_modalidade}
                    dataKey="quantidade"
                    nameKey="chave"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    // eslint-disable-next-line @typescript-eslint/no-explicit-any
                    label={(entry: any) => {
                      const d = entry?.payload ?? entry;
                      return `${String(d.chave ?? '')}: ${String(d.quantidade ?? '')}`;
                    }}
                    labelLine
                  >
                    {vitrine.distribuicao_modalidade.map((entry, index) => (
                      <Cell
                        key={entry.chave}
                        fill={
                          MODALIDADE_COLORS[
                            index % MODALIDADE_COLORS.length
                          ]
                        }
                      />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
