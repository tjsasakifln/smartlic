"use client";
/**
 * PREDINT-022 (#1671): OrgaoRecorrenteCard
 *
 * Cards de orgao com confidence, categoria principal, proxima janela estimada.
 * Bloco 2 da pagina /radar-recorrencia.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface OrgaoRecorrente {
  orgao: string;
  orgao_cnpj: string;
  confidence: number;
  categoria_principal: string;
  proxima_janela: string;
  contratos_ativos: number;
  valor_total: number;
}

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const MOCK_ORGAOS: OrgaoRecorrente[] = [
  {
    orgao: "Prefeitura Municipal de Sao Paulo",
    orgao_cnpj: "46288288000130",
    confidence: 0.92,
    categoria_principal: "Alimentos",
    proxima_janela: "Jul/2026",
    contratos_ativos: 45,
    valor_total: 28000000,
  },
  {
    orgao: "Secretaria de Saude de MG",
    orgao_cnpj: "17123456000100",
    confidence: 0.85,
    categoria_principal: "Saude",
    proxima_janela: "Ago/2026",
    contratos_ativos: 32,
    valor_total: 45000000,
  },
  {
    orgao: "Governo do Estado do RJ",
    orgao_cnpj: "28765432000155",
    confidence: 0.72,
    categoria_principal: "Engenharia",
    proxima_janela: "Set/2026",
    contratos_ativos: 28,
    valor_total: 52000000,
  },
  {
    orgao: "Secretaria de Educacao de SP",
    orgao_cnpj: "46321567000188",
    confidence: 0.65,
    categoria_principal: "Tecnologia",
    proxima_janela: "Out/2026",
    contratos_ativos: 18,
    valor_total: 8900000,
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatBRL(value: number): string {
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "bg-green-500";
  if (confidence >= 0.5) return "bg-yellow-500";
  return "bg-gray-300";
}

function confidenceTextColor(confidence: number): string {
  if (confidence >= 0.8) return "text-green-700";
  if (confidence >= 0.5) return "text-yellow-700";
  return "text-gray-500";
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function CardSkeleton() {
  return (
    <div className="bg-white rounded-lg shadow-sm border p-5 animate-pulse">
      <div className="h-5 w-3/4 bg-gray-100 rounded mb-3" />
      <div className="h-3 w-1/2 bg-gray-100 rounded mb-2" />
      <div className="h-2 bg-gray-100 rounded mb-3" />
      <div className="h-3 w-1/3 bg-gray-100 rounded" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface OrgaoRecorrenteCardProps {
  orgao: OrgaoRecorrente;
}

function OrgaoRecorrenteItem({ orgao }: OrgaoRecorrenteCardProps) {
  const percentage = Math.round(orgao.confidence * 100);
  return (
    <div className="bg-white rounded-lg shadow-sm border p-5 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <h4 className="text-sm font-semibold text-gray-900 leading-tight">
          {orgao.orgao}
        </h4>
        <span className={`text-xs font-bold whitespace-nowrap ml-2 ${confidenceTextColor(orgao.confidence)}`}>
          {percentage}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="h-2 bg-gray-100 rounded-full mb-3 overflow-hidden">
        <div
          className={`h-full rounded-full ${confidenceColor(orgao.confidence)}`}
          style={{ width: `${percentage}%` }}
          role="progressbar"
          aria-valuenow={percentage}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
        <div>
          <span className="block text-gray-400">Categoria</span>
          <span className="font-medium text-gray-700">{orgao.categoria_principal}</span>
        </div>
        <div>
          <span className="block text-gray-400">Proxima Janela</span>
          <span className="font-medium text-gray-700">{orgao.proxima_janela}</span>
        </div>
        <div>
          <span className="block text-gray-400">Contratos Ativos</span>
          <span className="font-medium text-gray-700">{orgao.contratos_ativos}</span>
        </div>
        <div>
          <span className="block text-gray-400">Valor Total</span>
          <span className="font-medium text-green-700">{formatBRL(orgao.valor_total)}</span>
        </div>
      </div>
    </div>
  );
}

interface OrgaosRecorrentesProps {
  orgaos?: OrgaoRecorrente[];
  loading?: boolean;
}

function OrgaosRecorrentes({
  orgaos,
  loading = false,
}: OrgaosRecorrentesProps) {
  const data = orgaos ?? MOCK_ORGAOS;
  const sorted = [...data].sort((a, b) => b.confidence - a.confidence);

  if (loading) {
    return (
      <div data-testid="orgaos-recorrentes" className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
    );
  }

  return (
    <div data-testid="orgaos-recorrentes" className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      {sorted.map((o, i) => (
        <OrgaoRecorrenteItem key={o.orgao_cnpj || i} orgao={o} />
      ))}
    </div>
  );
}

export { OrgaosRecorrentes, OrgaoRecorrenteItem };
export default OrgaosRecorrentes;
