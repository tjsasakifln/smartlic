"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../../components/AuthProvider";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Concorrente {
  nome: string;
  cnpj: string;
  valor_total_contratado: number;
  numero_contratos: number;
}

interface CentroGuerraData {
  edital_id: string;
  numero: string | null;
  objeto: string | null;
  valor_estimado: number | null;
  modalidade: string | null;
  orgao_nome: string | null;
  uf: string | null;
  data_publicacao: string | null;
  data_abertura: string | null;
  status: string | null;
  viabilidade_score: number | null;
  viabilidade_fatores: Record<string, number> | null;
  proximos_passos: string[];
  concorrentes: Concorrente[];
  na_watchlist: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value);
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

function statusBadgeClass(status: string | null): string {
  switch (status) {
    case "publicado":
      return "bg-blue-100 text-blue-800";
    case "aberto":
      return "bg-green-100 text-green-800";
    case "em_andamento":
      return "bg-yellow-100 text-yellow-800";
    case "suspenso":
      return "bg-orange-100 text-orange-800";
    case "adjudicado":
      return "bg-purple-100 text-purple-800";
    case "homologado":
      return "bg-teal-100 text-teal-800";
    case "cancelado":
      return "bg-red-100 text-red-800";
    default:
      return "bg-gray-100 text-gray-800";
  }
}

function statusLabel(status: string | null): string {
  const labels: Record<string, string> = {
    publicado: "Publicado",
    aberto: "Aberto",
    em_andamento: "Em Andamento",
    suspenso: "Suspenso",
    adjudicado: "Adjudicado",
    homologado: "Homologado",
    cancelado: "Cancelado",
  };
  return labels[status ?? ""] ?? status ?? "Indefinido";
}

function getViabilityColor(score: number | null): string {
  if (score === null) return "bg-gray-200";
  if (score >= 70) return "bg-green-500";
  if (score >= 40) return "bg-yellow-500";
  return "bg-red-500";
}

function getViabilityLabel(score: number | null): string {
  if (score === null) return "Nao avaliada";
  if (score >= 70) return "Alta";
  if (score >= 40) return "Media";
  return "Baixa";
}

// ---------------------------------------------------------------------------
// Info Card
// ---------------------------------------------------------------------------

function InfoCard({
  label,
  value,
}: {
  label: string;
  value: string | number | null;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p className="mt-1 text-base font-semibold text-gray-900">
        {value ?? "—"}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Barra de Viabilidade
// ---------------------------------------------------------------------------

function ViabilityBar({ score, fatores }: { score: number | null; fatores: Record<string, number> | null }) {
  if (score === null) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="text-sm text-gray-500">
          Este edital ainda nao foi analisado. Adicione ao pipeline para calcular a viabilidade.
        </p>
      </div>
    );
  }

  const factorLabels: Record<string, string> = {
    modalidade: "Modalidade (30%)",
    timeline: "Timeline (25%)",
    valor: "Valor (25%)",
    geografia: "Geografia (20%)",
  };

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-lg font-semibold text-gray-900">
          Score: {score.toFixed(0)}/100
        </span>
        <span
          className={`rounded-full px-3 py-1 text-sm font-medium ${
            score >= 70
              ? "bg-green-100 text-green-800"
              : score >= 40
                ? "bg-yellow-100 text-yellow-800"
                : "bg-red-100 text-red-800"
          }`}
        >
          {getViabilityLabel(score)}
        </span>
      </div>

      <div className="mb-4 h-3 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className={`h-full rounded-full transition-all ${getViabilityColor(score)}`}
          style={{ width: `${score}%` }}
        />
      </div>

      {fatores && (
        <div className="space-y-2">
          {Object.entries(factorLabels).map(([key, label]) => {
            const val = fatores[key];
            if (val === undefined) return null;
            return (
              <div key={key} className="flex items-center justify-between text-sm">
                <span className="text-gray-600">{label}</span>
                <div className="flex items-center gap-2">
                  <div className="h-2 w-24 overflow-hidden rounded-full bg-gray-200">
                    <div
                      className={`h-full rounded-full ${
                        val >= 70 ? "bg-green-500" : val >= 40 ? "bg-yellow-500" : "bg-red-500"
                      }`}
                      style={{ width: `${val}%` }}
                    />
                  </div>
                  <span className="w-8 text-right text-gray-700">{val.toFixed(0)}</span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Passos Card
// ---------------------------------------------------------------------------

function PassosCard({
  passos,
  onToggle,
  checked,
}: {
  passos: string[];
  onToggle: (index: number) => void;
  checked: boolean[];
}) {
  if (passos.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="text-sm text-gray-500">Nenhum passo definido.</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <ul className="space-y-3">
        {passos.map((passo, idx) => (
          <li key={idx} className="flex items-start gap-3">
            <input
              type="checkbox"
              checked={checked[idx] ?? false}
              onChange={() => onToggle(idx)}
              className="mt-0.5 h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span
              className={`text-sm ${
                checked[idx] ? "text-gray-400 line-through" : "text-gray-700"
              }`}
            >
              {passo}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tabela Concorrentes
// ---------------------------------------------------------------------------

function ConcorrentesTable({ items }: { items: Concorrente[] }) {
  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-white p-4">
        <p className="text-sm text-gray-500">
          Nenhum fornecedor encontrado para este orgao.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-gray-500">
              Fornecedor
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wide text-gray-500">
              Total Contratado
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wide text-gray-500">
              Contratos
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {items.map((c, idx) => (
            <tr key={c.cnpj || idx} className="hover:bg-gray-50">
              <td className="whitespace-nowrap px-4 py-3 text-sm font-medium text-gray-900">
                {c.nome}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                {formatCurrency(c.valor_total_contratado)}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-right text-sm text-gray-700">
                {c.numero_contratos}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function CentroGuerraPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [data, setData] = useState<CentroGuerraData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkedPassos, setCheckedPassos] = useState<boolean[]>([]);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      router.push("/login");
      return;
    }
  }, [user, authLoading, router]);

  useEffect(() => {
    if (authLoading || !user) return;

    setIsLoading(true);
    setError(null);

    fetch(`/api/workspace/centro-guerra/${encodeURIComponent(id)}`)
      .then((res) => {
        if (!res.ok) {
          if (res.status === 404) throw new Error("Edital nao encontrado.");
          throw new Error(`Erro ao carregar: ${res.status}`);
        }
        return res.json();
      })
      .then((json: CentroGuerraData) => {
        setData(json);
        setCheckedPassos(json.proximos_passos.map(() => false));
      })
      .catch((err: Error) => {
        setError(err.message);
      })
      .finally(() => {
        setIsLoading(false);
      });
  }, [id, user, authLoading]);

  const handleTogglePasso = (index: number) => {
    setCheckedPassos((prev) => {
      const next = [...prev];
      next[index] = !next[index];
      return next;
    });
  };

  // --- Loading state ---
  if (authLoading || isLoading) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <div className="text-center">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-4 border-gray-300 border-t-blue-600" />
          <p className="text-sm text-gray-500">Carregando detalhes do edital...</p>
        </div>
      </div>
    );
  }

  // --- Error state ---
  if (error || !data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-12">
        <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center">
          <h2 className="mb-2 text-lg font-semibold text-red-800">
            Erro ao carregar
          </h2>
          <p className="text-sm text-red-600">{error ?? "Dados nao disponiveis."}</p>
          <button
            type="button"
            onClick={() => router.push("/workspace")}
            className="mt-4 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            Voltar para Workspace
          </button>
        </div>
      </div>
    );
  }

  // --- Data state ---
  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      {/* Header */}
      <div className="mb-6">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">
            {data.numero ?? "Centro de Guerra"}
          </h1>
          <span
            className={`rounded-full px-3 py-1 text-xs font-medium ${statusBadgeClass(data.status)}`}
          >
            {statusLabel(data.status)}
          </span>
          {data.na_watchlist && (
            <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-800">
              Na Watchlist
            </span>
          )}
        </div>
        {data.objeto && (
          <p className="mt-2 text-sm text-gray-600">{data.objeto}</p>
        )}
      </div>

      {/* Info Grid */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-3">
        <InfoCard label="Modalidade" value={data.modalidade} />
        <InfoCard
          label="Valor Estimado"
          value={formatCurrency(data.valor_estimado)}
        />
        <InfoCard label="Orgao" value={data.orgao_nome} />
        <InfoCard label="UF" value={data.uf} />
        <InfoCard label="Publicacao" value={formatDate(data.data_publicacao)} />
        <InfoCard label="Abertura" value={formatDate(data.data_abertura)} />
      </div>

      {/* Viability */}
      <section className="mb-6">
        <h2 className="mb-3 text-lg font-semibold text-gray-900">
          Viabilidade
        </h2>
        <ViabilityBar score={data.viabilidade_score} fatores={data.viabilidade_fatores} />
      </section>

      {/* Proximos Passos */}
      <section className="mb-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Proximos Passos
          </h2>
        </div>
        <PassosCard
          passos={data.proximos_passos}
          onToggle={handleTogglePasso}
          checked={checkedPassos}
        />
      </section>

      {/* Concorrentes */}
      <section className="mb-6">
        <h2 className="mb-3 text-lg font-semibold text-gray-900">
          Concorrentes (Top 10)
        </h2>
        <ConcorrentesTable items={data.concorrentes} />
      </section>
    </div>
  );
}
