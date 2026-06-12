"use client";
/**
 * PREDINT-022 (#1671): RecorrenciaTable
 *
 * Tabela de contratos expirando, ranqueada por confidence decrescente.
 * Bloco 1 da pagina /radar-recorrencia.
 */
import { useState } from "react";
import Link from "next/link";
import useSWR from "swr";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ContratoExpirando {
  orgao: string;
  orgao_cnpj: string;
  fornecedor_atual: string;
  fornecedor_cnpj: string;
  objeto: string;
  valor: number;
  data_termino: string;
  confidence: number;
  categoria: string;
}

interface RecorrenciaData {
  contratos: ContratoExpirando[];
  total: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const JANELAS = [
  { value: 30, label: "30 dias" },
  { value: 60, label: "60 dias" },
  { value: 90, label: "90 dias" },
] as const;

const UFS = [
  "AC","AL","AP","AM","BA","CE","DF","ES","GO",
  "MA","MT","MS","MG","PA","PB","PR","PE","PI",
  "RJ","RN","RS","RO","RR","SC","SP","SE","TO",
] as const;

const SETORES_EXEMPLO = [
  "alimentos",
  "construcao-civil",
  "educacao",
  "energia",
  "engenharia",
  "saude",
  "seguranca",
  "tecnologia",
  "transporte",
  "vigilancia",
] as const;

// ---------------------------------------------------------------------------
// Mock data (placeholder until PREDINT-021 endpoint is merged)
// ---------------------------------------------------------------------------

const MOCK_CONTRATOS: ContratoExpirando[] = [
  {
    orgao: "Prefeitura Municipal de Sao Paulo",
    orgao_cnpj: "46288288000130",
    fornecedor_atual: "Alimentos SA",
    fornecedor_cnpj: "12345678000190",
    objeto: "Fornecimento de merenda escolar",
    valor: 2500000,
    data_termino: "2026-08-15",
    confidence: 0.92,
    categoria: "Alimentos",
  },
  {
    orgao: "Secretaria de Saude de MG",
    orgao_cnpj: "17123456000100",
    fornecedor_atual: "Servicos Medicos Ltda",
    fornecedor_cnpj: "98765432000110",
    objeto: "Prestacao de servicos hospitalares",
    valor: 5800000,
    data_termino: "2026-07-30",
    confidence: 0.85,
    categoria: "Saude",
  },
  {
    orgao: "Governo do Estado do RJ",
    orgao_cnpj: "28765432000155",
    fornecedor_atual: "Construcoes RJ Ltda",
    fornecedor_cnpj: "55667788000122",
    objeto: "Obras de infraestrutura urbana",
    valor: 12000000,
    data_termino: "2026-09-01",
    confidence: 0.78,
    categoria: "Engenharia",
  },
  {
    orgao: "Secretaria de Educacao de SP",
    orgao_cnpj: "46321567000188",
    fornecedor_atual: "Tecnologia Educacional Ltda",
    fornecedor_cnpj: "11223344000155",
    objeto: "Plataforma de ensino digital",
    valor: 890000,
    data_termino: "2026-07-10",
    confidence: 0.72,
    categoria: "Tecnologia",
  },
  {
    orgao: "Prefeitura de Belo Horizonte",
    orgao_cnpj: "18555666000199",
    fornecedor_atual: "Vigilancia Patrimonial Ltda",
    fornecedor_cnpj: "99887766000133",
    objeto: "Servicos de vigilancia predial",
    valor: 1200000,
    data_termino: "2026-08-20",
    confidence: 0.65,
    categoria: "Vigilancia",
  },
  {
    orgao: "Secretaria de Transporte de SP",
    orgao_cnpj: "46111222000177",
    fornecedor_atual: "Transportes Rapido Ltda",
    fornecedor_cnpj: "77441122000188",
    objeto: "Manutencao de frota oficial",
    valor: 3400000,
    data_termino: "2026-07-25",
    confidence: 0.58,
    categoria: "Transporte",
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatDate(dateStr: string): string {
  return new Date(dateStr + "T00:00:00").toLocaleDateString("pt-BR");
}

function ConfidenceBadge({ confidence }: { confidence: number }) {
  let color: string;
  let label: string;

  if (confidence >= 0.8) {
    color = "bg-green-100 text-green-700 border-green-200";
    label = "Alta";
  } else if (confidence >= 0.5) {
    color = "bg-yellow-100 text-yellow-700 border-yellow-200";
    label = "Media";
  } else {
    color = "bg-gray-100 text-gray-500 border-gray-200";
    label = "Baixa";
  }

  return (
    <span
      className={`inline-block text-xs font-semibold px-2 py-0.5 rounded-full border ${color}`}
    >
      {label} ({Math.round(confidence * 100)}%)
    </span>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function TableSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-sm border overflow-x-auto animate-pulse">
      <div className="h-10 bg-gray-100" />
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="h-16 border-t border-gray-100 flex items-center px-4 gap-4">
          <div className="flex-1 h-4 bg-gray-100 rounded" />
          <div className="w-32 h-4 bg-gray-100 rounded" />
          <div className="w-24 h-4 bg-gray-100 rounded" />
          <div className="w-20 h-4 bg-gray-100 rounded" />
          <div className="w-16 h-4 bg-gray-100 rounded" />
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

interface RecorrenciaTableProps {
  baseEndpoint?: string;
}

function RecorrenciaTable({ baseEndpoint = "/api/predictive/recorrencia" }: RecorrenciaTableProps) {
  const [ufFiltro, setUfFiltro] = useState<string>("");
  const [setorFiltro, setSetorFiltro] = useState<string>("");
  const [janela, setJanela] = useState<number>(60);

  // SWR fetch — falls back to mock data if endpoint unavailable
  const fetcher = async (url: string): Promise<RecorrenciaData> => {
    try {
      const resp = await fetch(url, { credentials: "include" });
      if (!resp.ok) throw new Error("API unavailable");
      return await resp.json();
    } catch {
      // Fallback to mock data
      return { contratos: MOCK_CONTRATOS, total: MOCK_CONTRATOS.length };
    }
  };

  const queryParams = new URLSearchParams({ janela: String(janela) });
  if (ufFiltro) queryParams.set("uf", ufFiltro);
  if (setorFiltro) queryParams.set("setor", setorFiltro);

  const { data, error, isLoading } = useSWR<RecorrenciaData>(
    `${baseEndpoint}?${queryParams.toString()}`,
    fetcher,
    { revalidateOnFocus: false, dedupingInterval: 60000 }
  );

  const contratos = data?.contratos ?? [];
  const sorted = [...contratos].sort((a, b) => b.confidence - a.confidence);

  if (isLoading) {
    return (
      <div data-testid="recorrencia-table">
        <div className="flex flex-wrap gap-3 mb-4">
          {filtrosSkeleton()}
        </div>
        <TableSkeleton />
      </div>
    );
  }

  if (error || contratos.length === 0) {
    return (
      <div
        data-testid="recorrencia-table"
        className="bg-gray-50 rounded-lg border p-6 text-center"
      >
        <div className="flex flex-wrap gap-3 mb-4 justify-center">
          {renderFiltros()}
        </div>
        <p className="text-gray-500 text-sm">
          Dados temporariamente indisponiveis.{" "}
          <button
            onClick={() => window.location.reload()}
            className="text-blue-600 hover:underline"
          >
            Tentar novamente
          </button>
        </p>
      </div>
    );
  }

  function renderFiltros() {
    return (
      <>
        {/* UF Filter */}
        <select
          value={ufFiltro}
          onChange={(e) => setUfFiltro(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm bg-white"
          data-testid="recorrencia-filtro-uf"
          aria-label="Filtrar por UF"
        >
          <option value="">Todas as UFs</option>
          {UFS.map((uf) => (
            <option key={uf} value={uf}>{uf}</option>
          ))}
        </select>

        {/* Sector Filter */}
        <select
          value={setorFiltro}
          onChange={(e) => setSetorFiltro(e.target.value)}
          className="border rounded-lg px-3 py-2 text-sm bg-white"
          data-testid="recorrencia-filtro-setor"
          aria-label="Filtrar por setor"
        >
          <option value="">Todos os setores</option>
          {SETORES_EXEMPLO.map((s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1).replace(/-/g, " ")}
            </option>
          ))}
        </select>

        {/* Window Filter */}
        <div className="flex gap-1" role="group" aria-label="Janela de tempo">
          {JANELAS.map((j) => (
            <button
              key={j.value}
              onClick={() => setJanela(j.value)}
              className={`px-3 py-2 text-sm rounded-lg border transition-colors ${
                janela === j.value
                  ? "bg-blue-600 text-white border-blue-600"
                  : "bg-white text-gray-600 border-gray-300 hover:bg-gray-50"
              }`}
              data-testid={`recorrencia-janela-${j.value}`}
            >
              {j.label}
            </button>
          ))}
        </div>
      </>
    );
  }

  function filtrosSkeleton() {
    return Array.from({ length: 3 }).map((_, i) => (
      <div key={i} className="h-10 w-32 bg-gray-100 rounded-lg animate-pulse" />
    ));
  }

  return (
    <div data-testid="recorrencia-table">
      <div className="flex flex-wrap gap-3 mb-4">
        {renderFiltros()}
      </div>

      <p className="text-sm text-gray-500 mb-3">
        {sorted.length} contrato{sorted.length !== 1 ? "s" : ""} encontrado
        {sorted.length !== 1 ? "s" : ""}
      </p>

      <div className="bg-white rounded-lg shadow-sm border overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-gray-600">
            <tr>
              <th className="text-left px-4 py-3">Orgao</th>
              <th className="text-left px-4 py-3">Objeto</th>
              <th className="text-left px-4 py-3">Fornecedor Atual</th>
              <th className="text-right px-4 py-3">Valor</th>
              <th className="text-right px-4 py-3">Termino</th>
              <th className="text-center px-4 py-3">Confianca</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {sorted.map((c, i) => (
              <tr key={`${c.fornecedor_cnpj}-${c.data_termino}-${i}`} className="hover:bg-gray-50">
                <td className="px-4 py-2">
                  <Link
                    href={`/orgaos/${c.orgao_cnpj}`}
                    className="text-blue-600 hover:underline font-medium"
                  >
                    {c.orgao}
                  </Link>
                </td>
                <td className="px-4 py-2 max-w-xs">
                  <span className="line-clamp-2 text-gray-700">{c.objeto}</span>
                </td>
                <td className="px-4 py-2">
                  <Link
                    href={`/fornecedores/${c.fornecedor_cnpj}`}
                    className="text-blue-600 hover:underline"
                  >
                    {c.fornecedor_atual}
                  </Link>
                </td>
                <td className="text-right px-4 py-2 text-green-700 whitespace-nowrap">
                  {formatBRL(c.valor)}
                </td>
                <td className="text-right px-4 py-2 text-gray-500 whitespace-nowrap">
                  {formatDate(c.data_termino)}
                </td>
                <td className="text-center px-4 py-2">
                  <ConfidenceBadge confidence={c.confidence} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export { RecorrenciaTable };
export default RecorrenciaTable;
