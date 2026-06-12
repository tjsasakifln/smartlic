/**
 * WIDGET-COMPINT-001: Widget builder/preview page.
 *
 * Allows users to select setor, UF, and tema to preview the widget,
 * then copy the embed iframe code.
 */

'use client';

import { useState, useCallback } from 'react';
import { SETORES_FALLBACK } from '@/app/buscar/hooks/filters/sectorData';

type WidgetTema = 'market-share' | 'top-winners' | 'monthly-trend' | 'orgao-ranking';

const TEMAS: { id: WidgetTema; label: string; desc: string }[] = [
  { id: 'market-share', label: 'Market Share', desc: 'Participação dos fornecedores no setor' },
  { id: 'top-winners', label: 'Top Vencedores', desc: 'Maiores vencedores de contratos' },
  { id: 'monthly-trend', label: 'Tendência Mensal', desc: 'Evolução mensal de contratos' },
  { id: 'orgao-ranking', label: 'Ranking de Órgãos', desc: 'Órgãos que mais compram no setor' },
];

const UFS = [
  'AC', 'AL', 'AP', 'AM', 'BA', 'CE', 'DF', 'ES', 'GO',
  'MA', 'MT', 'MS', 'MG', 'PA', 'PB', 'PR', 'PE', 'PI',
  'RJ', 'RN', 'RS', 'RO', 'RR', 'SC', 'SP', 'SE', 'TO',
];

const WIDGET_URL = process.env.NEXT_PUBLIC_WIDGET_URL || 'https://smartlic.tech';

export default function WidgetPreviewPage() {
  const [uf, setUf] = useState('');
  const [tema, setTema] = useState<WidgetTema>('market-share');
  const [copied, setCopied] = useState(false);

  const defaultSector = SETORES_FALLBACK.find(
    (s) => s.id === 'informatica'
  );
  const [selectedSetor, setSelectedSetor] = useState(
    defaultSector?.id || SETORES_FALLBACK[0]?.id || ''
  );

  const buildIframeUrl = useCallback(() => {
    const params = new URLSearchParams();
    params.set('setor', selectedSetor);
    params.set('tema', tema);
    if (uf) params.set('uf', uf);
    return `/widgets/competitive-intel?${params.toString()}`;
  }, [selectedSetor, tema, uf]);

  const buildEmbedCode = useCallback(() => {
    const iframeUrl = `${WIDGET_URL}${buildIframeUrl()}`;
    return `<iframe src="${iframeUrl}" width="100%" height="400" frameborder="0" style="border:1px solid #e5e7eb;border-radius:8px;" allow="autoplay"></iframe>`;
  }, [buildIframeUrl]);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(buildEmbedCode());
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const textarea = document.createElement('textarea');
      textarea.value = buildEmbedCode();
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <main className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <div className="max-w-5xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl md:text-3xl font-bold text-gray-900 dark:text-white mb-2">
            Widget de Inteligência Competitiva
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Crie um widget embedável com dados de Market Share e Inteligência
            Competitiva para contratos públicos. Incorpore no seu site, blog ou
            portal.
          </p>
        </div>

        <div className="grid md:grid-cols-3 gap-8">
          {/* Controls panel */}
          <div className="md:col-span-1 space-y-6">
            {/* Setor */}
            <div>
              <label htmlFor="setor-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Setor
              </label>
              <select
                id="setor-select"
                value={selectedSetor}
                onChange={(e) => setSelectedSetor(e.target.value)}
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white"
              >
                {SETORES_FALLBACK.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </div>

            {/* UF */}
            <div>
              <label htmlFor="uf-select" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                UF <span className="text-gray-400">(opcional)</span>
              </label>
              <select
                id="uf-select"
                value={uf}
                onChange={(e) => setUf(e.target.value)}
                className="w-full rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-800 px-3 py-2 text-sm text-gray-900 dark:text-white"
              >
                <option value="">Brasil (todos)</option>
                {UFS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            {/* Tema */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Tema
              </label>
              <div className="space-y-2">
                {TEMAS.map((t) => (
                  <button
                    key={t.id}
                    onClick={() => setTema(t.id)}
                    className={`w-full text-left px-3 py-2 rounded-lg text-sm border transition-colors ${
                      tema === t.id
                        ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-300 dark:border-blue-700 text-blue-700 dark:text-blue-300'
                        : 'bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-700 dark:text-gray-300 hover:border-blue-200'
                    }`}
                  >
                    <span className="font-medium">{t.label}</span>
                    <span className="block text-xs text-gray-400 mt-0.5">
                      {t.desc}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Preview + code */}
          <div className="md:col-span-2 space-y-6">
            {/* Preview */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800">
                <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Preview
                </h2>
              </div>
              <div className="p-4">
                <iframe
                  src={buildIframeUrl()}
                  width="100%"
                  height="400"
                  frameBorder="0"
                  title="Widget Preview"
                  style={{
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    maxWidth: '100%',
                  }}
                />
              </div>
            </div>

            {/* Embed code */}
            <div className="bg-white dark:bg-gray-900 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-100 dark:border-gray-800 flex items-center justify-between">
                <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                  Código de Embed
                </h2>
                <button
                  onClick={handleCopy}
                  className={`px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${
                    copied
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                      : 'bg-blue-600 text-white hover:bg-blue-700'
                  }`}
                >
                  {copied ? 'Copiado!' : 'Copiar'}
                </button>
              </div>
              <div className="p-4">
                <pre className="bg-gray-900 dark:bg-gray-800 rounded-lg p-4 text-xs text-green-400 overflow-x-auto whitespace-pre-wrap break-all">
                  {buildEmbedCode()}
                </pre>
              </div>
            </div>

            {/* Attribution note */}
            <div className="bg-blue-50 dark:bg-blue-900/20 rounded-xl border border-blue-100 dark:border-blue-800 p-4">
              <p className="text-sm text-blue-800 dark:text-blue-200">
                <strong>Atribuição obrigatória:</strong> O widget inclui
                automaticamente o link para SmartLic no rodapé. Mantenha este
                link para uso gratuito. Dados públicos via PNCP.
              </p>
            </div>
          </div>
        </div>

        {/* Back link */}
        <div className="mt-12 text-center">
          <a
            href="/"
            className="text-blue-600 dark:text-blue-400 hover:underline text-sm font-medium"
          >
            &larr; Voltar para SmartLic
          </a>
        </div>
      </div>
    </main>
  );
}
