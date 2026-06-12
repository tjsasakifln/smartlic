'use client';

import { useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import CompetitorSearch from './components/CompetitorSearch';
import CompetitorCard from './components/CompetitorCard';
import MarketShareChart from './components/MarketShareChart';
import SectorBenchmarkCard from './components/SectorBenchmarkCard';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CompetitorItem {
  cnpj: string;
  razao_social: string;
  total_contratado: number;
  numero_contratos: number;
  ticket_medio: number;
  ufs_atuacao: string[];
  market_share: number;
  tendencia: string;
}

interface BenchmarkMetric {
  metrica: string;
  label: string;
  valor_concorrente: number;
  percentil_concorrente: number;
  benchmark_setor: { p25: number; p50: number; p75: number };
  descricao: string;
}

interface TerritoryData {
  cnpj: string;
  razao_social: string;
  total_contratado: number;
  total_contratos: number;
  ufs: Array<{
    uf: string;
    total_contratado: number;
    numero_contratos: number;
    market_share: number;
    orgaos_principais: string[];
    tendencia: string;
  }>;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTORS = [
  { id: 'ti', name: 'Tecnologia da Informacao' },
  { id: 'saude', name: 'Saude' },
  { id: 'construcao', name: 'Construcao Civil' },
  { id: 'alimentos', name: 'Alimentos' },
  { id: 'limpeza', name: 'Limpeza e Conservacao' },
  { id: 'seguranca', name: 'Seguranca' },
  { id: 'transporte', name: 'Transporte' },
  { id: 'educacao', name: 'Educacao' },
  { id: 'energia', name: 'Energia' },
  { id: 'meio_ambiente', name: 'Meio Ambiente' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function IntelConcorrenteClient() {
  const [selectedSector, setSelectedSector] = useState('ti');
  const [selectedUF, setSelectedUF] = useState('');
  const [competitors, setCompetitors] = useState<CompetitorItem[]>([]);
  const [territory, setTerritory] = useState<TerritoryData | null>(null);
  const [benchmarks, setBenchmarks] = useState<BenchmarkMetric[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cnpjSearched, setCnpjSearched] = useState('');

  const handleSearch = useCallback(async (cnpj: string) => {
    setLoading(true);
    setError(null);
    setCnpjSearched(cnpj);

    try {
      // Fetch territory data
      const territoryRes = await fetch(`/api/intel-concorrente/territory/${cnpj}`);
      if (!territoryRes.ok) {
        throw new Error('Falha ao carregar dados do concorrente');
      }
      const territoryData: TerritoryData = await territoryRes.json();
      setTerritory(territoryData);

      // Fetch benchmarks
      const benchRes = await fetch(
        `/api/intel-concorrente/benchmarks?cnpj=${cnpj}&setor=${selectedSector}`
      );
      if (benchRes.ok) {
        const benchData = await benchRes.json();
        setBenchmarks(benchData.metricas || []);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar dados');
    } finally {
      setLoading(false);
    }
  }, [selectedSector]);

  const loadLandscape = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams({ setor: selectedSector });
      if (selectedUF) params.set('uf', selectedUF);

      const res = await fetch(`/api/intel-concorrente/landscape?${params}`);
      if (!res.ok) {
        throw new Error('Falha ao carregar paisagem competitiva');
      }
      const data = await res.json();
      setCompetitors(data.top_concorrentes || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar dados');
      setCompetitors([]);
    } finally {
      setLoading(false);
    }
  }, [selectedSector, selectedUF]);

  return (
    <main className="min-h-screen bg-gray-50 py-8">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8 text-center"
        >
          <h1 className="text-3xl font-bold text-gray-900 sm:text-4xl">
            Inteligencia Concorrencial
          </h1>
          <p className="mt-3 text-lg text-gray-600">
            Analise concorrentes, mapeie territorio e compare performance no mercado de compras publicas
          </p>
        </motion.div>

        {/* Sector Selector */}
        <div className="mb-6 rounded-lg bg-white p-4 shadow-sm">
          <label className="block text-sm font-medium text-gray-700">
            Setor
          </label>
          <select
            value={selectedSector}
            onChange={(e) => {
              setSelectedSector(e.target.value);
              setCompetitors([]);
              setTerritory(null);
            }}
            className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-blue-500 sm:text-sm"
          >
            {SECTORS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>

          {/* UF filter */}
          <div className="mt-3">
            <label className="block text-sm font-medium text-gray-700">
              Filtrar por UF (opcional)
            </label>
            <input
              type="text"
              value={selectedUF}
              onChange={(e) => setSelectedUF(e.target.value.toUpperCase())}
              placeholder="Ex: SP, RJ, MG"
              maxLength={2}
              className="mt-1 block w-32 rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-blue-500 sm:text-sm"
            />
          </div>

          <button
            onClick={loadLandscape}
            disabled={loading}
            className="mt-3 inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {loading ? 'Carregando...' : 'Carregar Panorama'}
          </button>
        </div>

        {/* Error state */}
        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            {error}
            <button
              onClick={() => setError(null)}
              className="ml-3 underline hover:text-red-900"
            >
              Fechar
            </button>
          </div>
        )}

        {/* Competitor Search */}
        <div className="mb-6">
          <CompetitorSearch onSearch={handleSearch} loading={loading} />
        </div>

        {/* Grid Layout */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Competitor Card */}
          {territory && (
            <div className="lg:col-span-1">
              <CompetitorCard
                razao_social={territory.razao_social}
                cnpj={territory.cnpj}
                total_contratado={territory.total_contratado}
                total_contratos={territory.total_contratos}
                ufs_count={territory.ufs.length}
                tendencia="estavel"
              />
            </div>
          )}

          {/* Market Share Chart */}
          <div className="lg:col-span-2">
            <MarketShareChart competitors={competitors} />
          </div>
        </div>

        {/* Territory Table */}
        {territory && territory.ufs.length > 0 && (
          <div className="mt-6 overflow-x-auto rounded-lg bg-white p-4 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Presenca por UF
            </h2>
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    UF
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Valor Contratado (R$)
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Contratos
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Market Share
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {territory.ufs.map((uf) => (
                  <tr key={uf.uf} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                      {uf.uf}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                      {uf.total_contratado.toLocaleString('pt-BR', {
                        style: 'currency',
                        currency: 'BRL',
                      })}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                      {uf.numero_contratos}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                      {uf.market_share.toFixed(1)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Sector Benchmarks */}
        {benchmarks.length > 0 && (
          <div className="mt-6">
            <SectorBenchmarkCard metricas={benchmarks} />
          </div>
        )}

        {/* Leaderboard */}
        {competitors.length > 0 && (
          <div className="mt-6 overflow-x-auto rounded-lg bg-white p-4 shadow-sm">
            <h2 className="mb-4 text-lg font-semibold text-gray-900">
              Ranking de Concorrentes
            </h2>
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
                    Concorrente
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Total Contratado
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Contratos
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Ticket Medio
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
                    Market Share
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium uppercase tracking-wider text-gray-500">
                    UFs
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {competitors.slice(0, 20).map((comp, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                      {idx + 1}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                      {comp.razao_social}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                      {comp.total_contratado.toLocaleString('pt-BR', {
                        style: 'currency',
                        currency: 'BRL',
                      })}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                      {comp.numero_contratos}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                      {comp.ticket_medio.toLocaleString('pt-BR', {
                        style: 'currency',
                        currency: 'BRL',
                      })}
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                      <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                        {comp.market_share.toFixed(1)}%
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-center text-sm text-gray-700">
                      {comp.ufs_atuacao.join(', ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && competitors.length === 0 && !territory && (
          <div className="rounded-lg border-2 border-dashed border-gray-300 p-12 text-center">
            <h3 className="text-lg font-medium text-gray-900">
              Bem-vindo a Inteligencia Concorrencial
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              Selecione um setor e clique em &quot;Carregar Panorama&quot; para ver o ranking de
              concorrentes, ou busque por um CNPJ especifico para analisar um concorrente em
              detalhes.
            </p>
          </div>
        )}
      </div>
    </main>
  );
}
