/**
 * WIDGET-COMPINT-001: Embdeddable iframe widget page.
 *
 * This page is designed to be embedded via <iframe> on external sites.
 * It reads query params (?setor=X&uf=Y&tema=Z), fetches data from the
 * backend, and renders a themed widget with light/dark mode support.
 *
 * Minimal chrome — only the widget content + required footer attribution.
 */

'use client';

import { useEffect, useState, useCallback } from 'react';

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || 'https://api.smartlic.tech';

type WidgetTema = 'market-share' | 'top-winners' | 'monthly-trend' | 'orgao-ranking';

interface WidgetData {
  tema: string;
  setor: string;
  uf?: string | null;
  periodo: string;
  dados: Record<string, unknown>;
}

type MarketShareWidgetProps = {
  dados: {
    valor_total: number;
    total_contratos: number;
    top_fornecedores: Array<{
      nome: string;
      percentual: number;
      valor: number;
      contratos: number;
    }>;
    concentracao: string;
  };
  setor: string;
  uf?: string | null;
  periodo: string;
};

type TopWinnersWidgetProps = {
  dados: { winners: Array<{ nome: string; contratos: number; valor_total: number; crescimento?: string | null }> };
  setor: string;
  uf?: string | null;
  periodo: string;
};

type MonthlyTrendWidgetProps = {
  dados: {
    serie: Array<{ mes: string; valor: number; contratos: number }>;
    tendencia: string;
  };
  setor: string;
  uf?: string | null;
  periodo: string;
};

type OrgaoRankingWidgetProps = {
  dados: { orgaos: Array<{ nome: string; valor: number; contratos: number }> };
  setor: string;
  uf?: string | null;
  periodo: string;
};

// ---------- Formatting helpers ----------

function fmtBRL(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(value);
}

function fmtPct(value: number): string {
  return `${value.toFixed(1).replace('.', ',')}%`;
}

function fmtNumber(value: number): string {
  return new Intl.NumberFormat('pt-BR').format(value);
}

// ---------- Theme renderers ----------

function MarketShareWidget({
  dados,
  setor,
  uf,
  periodo,
}: MarketShareWidgetProps) {
  const maxPct = Math.max(...dados.top_fornecedores.map((f) => f.percentual), 1);

  return (
    <div className="widget-body">
      <h2 className="widget-title">
        Market Share — {setor}
        {uf ? ` (${uf})` : ' (Brasil)'}
      </h2>
      <p className="widget-period">{periodo}</p>

      {/* Summary metrics */}
      <div className="widget-metrics">
        <div className="metric-box">
          <span className="metric-value">{fmtBRL(dados.valor_total)}</span>
          <span className="metric-label">Valor total</span>
        </div>
        <div className="metric-box">
          <span className="metric-value">{fmtNumber(dados.total_contratos)}</span>
          <span className="metric-label">Contratos</span>
        </div>
        <div className="metric-box">
          <span className="metric-value">{dados.concentracao}</span>
          <span className="metric-label">Concentração</span>
        </div>
      </div>

      {/* Top suppliers */}
      <div className="widget-section">
        <h3 className="widget-section-title">Top Fornecedores</h3>
        {dados.top_fornecedores.map((f, i) => (
          <div key={i} className="supplier-row">
            <div className="supplier-info">
              <span className="supplier-rank">{i + 1}</span>
              <span className="supplier-name">{f.nome}</span>
            </div>
            <div className="supplier-bar-wrapper">
              <div
                className="supplier-bar"
                style={{ width: `${(f.percentual / maxPct) * 100}%` }}
              />
            </div>
            <div className="supplier-values">
              <span className="supplier-pct">{fmtPct(f.percentual)}</span>
              <span className="supplier-val">{fmtBRL(f.valor)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopWinnersWidget({
  dados,
  setor,
  uf,
  periodo,
}: TopWinnersWidgetProps) {
  return (
    <div className="widget-body">
      <h2 className="widget-title">
        Top Vencedores — {setor}
        {uf ? ` (${uf})` : ' (Brasil)'}
      </h2>
      <p className="widget-period">{periodo}</p>

      <div className="widget-section">
        {dados.winners.map((w, i) => (
          <div key={i} className="winner-row">
            <span className="winner-rank">#{i + 1}</span>
            <div className="winner-info">
              <span className="winner-name">{w.nome}</span>
              <span className="winner-detail">
                {fmtNumber(w.contratos)} contratos &middot; {fmtBRL(w.valor_total)}
              </span>
            </div>
            {w.crescimento && (
              <span className="winner-growth">{w.crescimento}</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function MonthlyTrendWidget({
  dados,
  setor,
  uf,
  periodo,
}: MonthlyTrendWidgetProps) {
  const maxValor = Math.max(...dados.serie.map((m) => m.valor), 1);

  const tendenciaLabel: Record<string, string> = {
    crescimento: 'em crescimento',
    estavel: 'estável',
    queda: 'em queda',
  };

  return (
    <div className="widget-body">
      <h2 className="widget-title">
        Tendência Mensal — {setor}
        {uf ? ` (${uf})` : ' (Brasil)'}
      </h2>
      <p className="widget-period">{periodo}</p>

      {/* Trend badge */}
      <div className="trend-badge">
        Tendência: <strong>{tendenciaLabel[dados.tendencia] || dados.tendencia}</strong>
      </div>

      {/* Mini bar chart */}
      <div className="widget-section">
        <div className="trend-chart">
          {dados.serie.map((m, i) => (
            <div key={i} className="trend-bar-wrapper" title={`${m.mes}: ${fmtBRL(m.valor)}`}>
              <div
                className="trend-bar"
                style={{ height: `${(m.valor / maxValor) * 100}%` }}
              />
              {i % 3 === 0 && <span className="trend-label">{m.mes.slice(5)}</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Latest months */}
      <div className="widget-section">
        <h3 className="widget-section-title">Últimos meses</h3>
        {dados.serie.slice(-6).reverse().map((m, i) => (
          <div key={i} className="month-row">
            <span className="month-name">{m.mes}</span>
            <span className="month-val">{fmtBRL(m.valor)}</span>
            <span className="month-count">{fmtNumber(m.contratos)} contratos</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function OrgaoRankingWidget({
  dados,
  setor,
  uf,
  periodo,
}: OrgaoRankingWidgetProps) {
  const maxValor = Math.max(...dados.orgaos.map((o) => o.valor), 1);

  return (
    <div className="widget-body">
      <h2 className="widget-title">
        Ranking de Órgãos — {setor}
        {uf ? ` (${uf})` : ' (Brasil)'}
      </h2>
      <p className="widget-period">{periodo}</p>

      <div className="widget-section">
        {dados.orgaos.map((o, i) => (
          <div key={i} className="orgao-row">
            <span className="orgao-rank">{i + 1}</span>
            <div className="orgao-info">
              <span className="orgao-name">{o.nome}</span>
              <div className="orgao-bar-wrapper">
                <div
                  className="orgao-bar"
                  style={{ width: `${(o.valor / maxValor) * 100}%` }}
                />
              </div>
            </div>
            <div className="orgao-values">
              <span className="orgao-val">{fmtBRL(o.valor)}</span>
              <span className="orgao-count">{fmtNumber(o.contratos)} contratos</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------- Main widget component ----------

function WidgetContent({ tema, data }: { tema: WidgetTema; data: WidgetData }) {
  const { dados, setor, uf, periodo } = data;

  switch (tema) {
    case 'market-share':
      return (
        <MarketShareWidget
          dados={dados as MarketShareWidgetProps['dados']}
          setor={setor}
          uf={uf}
          periodo={periodo}
        />
      );
    case 'top-winners':
      return (
        <TopWinnersWidget
          dados={dados as TopWinnersWidgetProps['dados']}
          setor={setor}
          uf={uf}
          periodo={periodo}
        />
      );
    case 'monthly-trend':
      return (
        <MonthlyTrendWidget
          dados={dados as MonthlyTrendWidgetProps['dados']}
          setor={setor}
          uf={uf}
          periodo={periodo}
        />
      );
    case 'orgao-ranking':
      return (
        <OrgaoRankingWidget
          dados={dados as OrgaoRankingWidgetProps['dados']}
          setor={setor}
          uf={uf}
          periodo={periodo}
        />
      );
    default:
      return <p className="widget-error">Tema desconhecido: {tema}</p>;
  }
}

// ---------- Page component ----------

export default function WidgetCompetitiveIntelPage() {
  const [data, setData] = useState<WidgetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchWidgetData = useCallback(async () => {
    const params = new URLSearchParams(window.location.search);
    const setor = params.get('setor');
    const tema = params.get('tema');
    const uf = params.get('uf');

    if (!setor || !tema) {
      setError('Parâmetros obrigatórios: setor e tema');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const url = `${BACKEND_URL}/v1/widget/competitive-intel?setor=${encodeURIComponent(setor)}&tema=${encodeURIComponent(tema)}${uf ? `&uf=${encodeURIComponent(uf)}` : ''}`;
      const resp = await fetch(url, { signal: AbortSignal.timeout(15000) });

      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error((errBody as { message?: string }).message || 'Erro ao carregar dados');
      }

      const json = (await resp.json()) as WidgetData;
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro de conexão');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWidgetData();
  }, [fetchWidgetData]);

  return (
    <div className="widget-container">
      {/* Loading */}
      {loading && (
        <div className="widget-loading">
          <div className="spinner" />
          <p>Carregando dados...</p>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="widget-empty">
          <p className="widget-error">{error}</p>
        </div>
      )}

      {/* Data */}
      {data && !loading && (
        <>
          <WidgetContent tema={data.tema as WidgetTema} data={data} />
          {/* Footer attribution — REQUIRED backlink per CC BY 4.0 */}
          <footer className="widget-footer">
            <p>
              Dados por{' '}
              <a
                href="https://smartlic.tech"
                target="_blank"
                rel="noopener"
              >
                SmartLic — Inteligência em Compras Públicas
              </a>
            </p>
          </footer>
        </>
      )}

      <style jsx>{`
        .widget-container {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          background: var(--widget-bg, #ffffff);
          color: var(--widget-text, #1f2937);
          padding: 16px;
          min-height: 100vh;
          box-sizing: border-box;
        }

        .widget-body {
          max-width: 100%;
        }

        .widget-title {
          font-size: 16px;
          font-weight: 700;
          margin: 0 0 4px;
          color: var(--widget-title, #111827);
          line-height: 1.3;
        }

        .widget-period {
          font-size: 12px;
          color: var(--widget-muted, #6b7280);
          margin: 0 0 16px;
        }

        .widget-metrics {
          display: flex;
          gap: 8px;
          margin-bottom: 20px;
          flex-wrap: wrap;
        }

        .metric-box {
          flex: 1;
          min-width: 80px;
          background: var(--widget-card-bg, #f3f4f6);
          border-radius: 8px;
          padding: 10px 8px;
          text-align: center;
        }

        .metric-value {
          display: block;
          font-size: 16px;
          font-weight: 700;
          color: var(--widget-primary, #2563eb);
          line-height: 1.2;
        }

        .metric-label {
          display: block;
          font-size: 10px;
          color: var(--widget-muted, #6b7280);
          margin-top: 2px;
          text-transform: uppercase;
          letter-spacing: 0.03em;
        }

        .widget-section {
          margin-top: 16px;
        }

        .widget-section-title {
          font-size: 13px;
          font-weight: 600;
          color: var(--widget-title, #111827);
          margin: 0 0 10px;
          text-transform: uppercase;
          letter-spacing: 0.03em;
        }

        /* Supplier rows */
        .supplier-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 8px;
        }

        .supplier-info {
          display: flex;
          align-items: center;
          gap: 6px;
          min-width: 0;
          flex: 1;
        }

        .supplier-rank {
          font-size: 11px;
          font-weight: 700;
          color: var(--widget-muted, #9ca3af);
          width: 18px;
          text-align: right;
          flex-shrink: 0;
        }

        .supplier-name {
          font-size: 12px;
          font-weight: 500;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .supplier-bar-wrapper {
          flex: 2;
          height: 8px;
          background: var(--widget-card-bg, #e5e7eb);
          border-radius: 4px;
          overflow: hidden;
          min-width: 40px;
        }

        .supplier-bar {
          height: 100%;
          background: var(--widget-primary, #2563eb);
          border-radius: 4px;
          transition: width 0.3s ease;
        }

        .supplier-values {
          display: flex;
          gap: 8px;
          align-items: center;
          flex-shrink: 0;
        }

        .supplier-pct {
          font-size: 12px;
          font-weight: 600;
          color: var(--widget-primary, #2563eb);
          min-width: 40px;
          text-align: right;
        }

        .supplier-val {
          font-size: 11px;
          color: var(--widget-muted, #6b7280);
          min-width: 70px;
          text-align: right;
        }

        /* Winner rows */
        .winner-row {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 8px 0;
          border-bottom: 1px solid var(--widget-border, #f3f4f6);
        }

        .winner-row:last-child {
          border-bottom: none;
        }

        .winner-rank {
          font-size: 14px;
          font-weight: 700;
          color: var(--widget-primary, #2563eb);
          width: 28px;
          flex-shrink: 0;
        }

        .winner-info {
          flex: 1;
          min-width: 0;
        }

        .winner-name {
          display: block;
          font-size: 13px;
          font-weight: 600;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .winner-detail {
          display: block;
          font-size: 11px;
          color: var(--widget-muted, #6b7280);
          margin-top: 1px;
        }

        .winner-growth {
          font-size: 12px;
          font-weight: 600;
          color: #059669;
          flex-shrink: 0;
        }

        /* Trend chart */
        .trend-badge {
          font-size: 13px;
          color: var(--widget-muted, #6b7280);
          margin-bottom: 16px;
          padding: 8px 12px;
          background: var(--widget-card-bg, #f3f4f6);
          border-radius: 6px;
          display: inline-block;
        }

        .trend-chart {
          display: flex;
          align-items: flex-end;
          gap: 2px;
          height: 100px;
          padding: 8px 0;
        }

        .trend-bar-wrapper {
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          height: 100%;
          justify-content: flex-end;
        }

        .trend-bar {
          width: 100%;
          min-height: 2px;
          background: var(--widget-primary, #2563eb);
          border-radius: 2px 2px 0 0;
          transition: height 0.3s ease;
        }

        .trend-label {
          font-size: 8px;
          color: var(--widget-muted, #9ca3af);
          margin-top: 4px;
        }

        .month-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 6px 0;
          border-bottom: 1px solid var(--widget-border, #f3f4f6);
          font-size: 12px;
        }

        .month-name {
          font-weight: 600;
          min-width: 55px;
        }

        .month-val {
          flex: 1;
          text-align: right;
          font-weight: 500;
        }

        .month-count {
          color: var(--widget-muted, #6b7280);
          min-width: 80px;
          text-align: right;
        }

        /* Orgao rows */
        .orgao-row {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 10px;
        }

        .orgao-rank {
          font-size: 11px;
          font-weight: 700;
          color: var(--widget-muted, #9ca3af);
          width: 18px;
          text-align: right;
          flex-shrink: 0;
        }

        .orgao-info {
          flex: 1;
          min-width: 0;
        }

        .orgao-name {
          display: block;
          font-size: 12px;
          font-weight: 500;
          margin-bottom: 3px;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
        }

        .orgao-bar-wrapper {
          height: 6px;
          background: var(--widget-card-bg, #e5e7eb);
          border-radius: 3px;
          overflow: hidden;
        }

        .orgao-bar {
          height: 100%;
          background: var(--widget-primary, #2563eb);
          border-radius: 3px;
          transition: width 0.3s ease;
        }

        .orgao-values {
          text-align: right;
          flex-shrink: 0;
        }

        .orgao-val {
          display: block;
          font-size: 12px;
          font-weight: 600;
        }

        .orgao-count {
          display: block;
          font-size: 10px;
          color: var(--widget-muted, #6b7280);
        }

        /* Loading */
        .widget-loading {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 40px 16px;
          gap: 12px;
        }

        .widget-loading p {
          font-size: 13px;
          color: var(--widget-muted, #6b7280);
        }

        .spinner {
          width: 24px;
          height: 24px;
          border: 3px solid var(--widget-card-bg, #e5e7eb);
          border-top-color: var(--widget-primary, #2563eb);
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .widget-empty {
          display: flex;
          align-items: center;
          justify-content: center;
          padding: 40px 16px;
        }

        .widget-error {
          font-size: 13px;
          color: #ef4444;
          text-align: center;
        }

        /* Footer — REQUIRED attribution */
        .widget-footer {
          margin-top: 24px;
          padding-top: 12px;
          border-top: 1px solid var(--widget-border, #e5e7eb);
          text-align: center;
        }

        .widget-footer p {
          font-size: 11px;
          color: var(--widget-muted, #9ca3af);
          margin: 0;
        }

        .widget-footer a {
          color: var(--widget-primary, #2563eb);
          text-decoration: none;
          font-weight: 500;
        }

        .widget-footer a:hover {
          text-decoration: underline;
        }

        /* Responsive */
        @media (max-width: 400px) {
          .widget-container {
            padding: 12px;
          }
          .widget-title {
            font-size: 14px;
          }
          .supplier-val {
            display: none;
          }
          .orgao-count {
            display: none;
          }
        }
      `}</style>
      <style jsx global>{`
        :root {
          --widget-bg: #ffffff;
          --widget-text: #1f2937;
          --widget-title: #111827;
          --widget-muted: #6b7280;
          --widget-primary: #2563eb;
          --widget-card-bg: #f3f4f6;
          --widget-border: #e5e7eb;
        }

        @media (prefers-color-scheme: dark) {
          :root {
            --widget-bg: #1f2937;
            --widget-text: #e5e7eb;
            --widget-title: #f9fafb;
            --widget-muted: #9ca3af;
            --widget-primary: #60a5fa;
            --widget-card-bg: #374151;
            --widget-border: #4b5563;
          }
        }

        body {
          margin: 0;
          padding: 0;
          background: var(--widget-bg);
        }
      `}</style>
    </div>
  );
}
