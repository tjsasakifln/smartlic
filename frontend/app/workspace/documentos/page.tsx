"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "../../components/AuthProvider";
import { AuthLoadingScreen } from "../../../components/AuthLoadingScreen";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TemplateItem {
  id: string;
  nome: string;
  tipo: string;
  descricao?: string | null;
  conteudo: string;
  created_at: string;
}

interface DocumentoItem {
  id: string;
  user_id: string;
  edital_id?: string | null;
  template_id?: string | null;
  titulo: string;
  conteudo: string;
  tipo: string;
  variaveis: Record<string, string>;
  created_at: string;
  updated_at: string;
}

const TIPO_BADGE_COLORS: Record<string, string> = {
  proposta: "bg-blue-100 text-blue-800",
  declaracao: "bg-green-100 text-green-800",
  recurso: "bg-yellow-100 text-yellow-800",
  impugnacao: "bg-red-100 text-red-800",
  carta: "bg-purple-100 text-purple-800",
  planilha: "bg-gray-100 text-gray-800",
};

const TIPO_LABELS: Record<string, string> = {
  proposta: "Proposta",
  declaracao: "Declaracao",
  recurso: "Recurso",
  impugnacao: "Impugnacao",
  carta: "Carta",
  planilha: "Planilha",
};

// ---------------------------------------------------------------------------
// Create Document Modal
// ---------------------------------------------------------------------------

function CreateDocumentoModal({
  open,
  onClose,
  onCreated,
}: {
  open: boolean;
  onClose: () => void;
  onCreated: () => void;
}) {
  const [titulo, setTitulo] = useState("");
  const [tipo, setTipo] = useState("proposta");
  const [templateId, setTemplateId] = useState("");
  const [editalId, setEditalId] = useState("");
  const [templates, setTemplates] = useState<TemplateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    (async () => {
      try {
        const res = await fetch("/api/workspace/templates");
        if (res.ok) {
          setTemplates(await res.json());
        }
      } catch {
        // templates are optional — no error if fetch fails
      }
    })();
  }, [open]);

  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!titulo.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const body: Record<string, string> = { titulo: titulo.trim(), tipo };
      if (templateId) body.template_id = templateId;
      if (editalId.trim()) body.edital_id = editalId.trim();

      const res = await fetch("/api/workspace/documentos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || data.detail || "Erro ao criar documento");
      }

      setTitulo("");
      setTipo("proposta");
      setTemplateId("");
      setEditalId("");
      onCreated();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar documento");
    } finally {
      setLoading(false);
    }
  }, [titulo, tipo, templateId, editalId, onCreated, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl max-w-lg w-full mx-4 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-[var(--ink)]">Novo Documento</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-[var(--ink-secondary)] mb-1">
              Titulo
            </label>
            <input
              type="text"
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ex: Proposta Comercial - Edital 001/2026"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-[var(--ink-secondary)] mb-1">
              Tipo
            </label>
            <select
              value={tipo}
              onChange={(e) => setTipo(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {Object.entries(TIPO_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          {templates.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-[var(--ink-secondary)] mb-1">
                Template (opcional)
              </label>
              <select
                value={templateId}
                onChange={(e) => setTemplateId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Nenhum</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>{t.nome}</option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-[var(--ink-secondary)] mb-1">
              ID do Edital (opcional)
            </label>
            <input
              type="text"
              value={editalId}
              onChange={(e) => setEditalId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Ex: 12345678901234567890123456789012345678901234"
            />
          </div>

          {error && (
            <p className="text-sm text-red-600">{error}</p>
          )}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading || !titulo.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? "Criando..." : "Criar Documento"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function DocumentosPage() {
  const { session, loading: authLoading } = useAuth();
  const router = useRouter();

  const [documentos, setDocumentos] = useState<DocumentoItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [filterTipo, setFilterTipo] = useState<string>("");

  const fetchDocumentos = useCallback(async () => {
    setLoadingDocs(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      params.set("limit", "50");
      if (filterTipo) params.set("tipo", filterTipo);

      const res = await fetch(`/api/workspace/documentos?${params.toString()}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || data.detail || "Erro ao carregar documentos");
      }

      const data = await res.json();
      setDocumentos(data.documentos || []);
      setTotal(data.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar documentos");
    } finally {
      setLoadingDocs(false);
    }
  }, [filterTipo]);

  useEffect(() => {
    if (session) fetchDocumentos();
  }, [session, fetchDocumentos]);

  const handleDelete = useCallback(async (id: string) => {
    if (!confirm("Tem certeza que deseja excluir este documento?")) return;

    try {
      const res = await fetch(`/api/workspace/documentos/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || "Erro ao excluir");
      }
      fetchDocumentos();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao excluir documento");
    }
  }, [fetchDocumentos]);

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  if (authLoading) return <AuthLoadingScreen />;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-semibold text-[var(--ink)]">
            Documentos
          </h1>
          <p className="mt-1 text-sm text-[var(--ink-secondary)]">
            Crie e edite documentos para suas licitacoes.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700"
        >
          + Novo Documento
        </button>
      </div>

      {/* Filter */}
      <div className="flex gap-2 items-center">
        <label className="text-sm font-medium text-[var(--ink-secondary)]">Filtrar:</label>
        <select
          value={filterTipo}
          onChange={(e) => setFilterTipo(e.target.value)}
          className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">Todos os tipos</option>
          {Object.entries(TIPO_LABELS).map(([value, label]) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>

      {/* Error */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
          <button onClick={fetchDocumentos} className="ml-3 underline hover:no-underline">
            Tentar novamente
          </button>
        </div>
      )}

      {/* Loading */}
      {loadingDocs && (
        <div className="text-center py-12 text-[var(--ink-secondary)]">
          Carregando documentos...
        </div>
      )}

      {/* Empty */}
      {!loadingDocs && !error && documentos.length === 0 && (
        <div className="text-center py-12">
          <p className="text-[var(--ink-secondary)] mb-4">
            Nenhum documento encontrado.
          </p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 text-sm font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50"
          >
            Criar primeiro documento
          </button>
        </div>
      )}

      {/* Document Cards */}
      {!loadingDocs && documentos.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {documentos.map((doc) => (
            <div
              key={doc.id}
              className="border border-gray-200 rounded-xl p-4 hover:shadow-md transition-shadow cursor-pointer bg-white"
              onClick={() => router.push(`/workspace/documentos/${doc.id}`)}
            >
              <div className="flex items-start justify-between mb-2">
                <span
                  className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full ${
                    TIPO_BADGE_COLORS[doc.tipo] || "bg-gray-100 text-gray-800"
                  }`}
                >
                  {TIPO_LABELS[doc.tipo] || doc.tipo}
                </span>
              </div>

              <h3 className="font-medium text-[var(--ink)] truncate">
                {doc.titulo}
              </h3>

              {doc.edital_id && (
                <p className="mt-1 text-xs text-[var(--ink-secondary)] truncate">
                  Edital: {doc.edital_id}
                </p>
              )}

              <p className="mt-2 text-xs text-[var(--ink-secondary)]">
                Atualizado: {formatDate(doc.updated_at)}
              </p>

              <div className="mt-3 flex gap-2">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    router.push(`/workspace/documentos/${doc.id}`);
                  }}
                  className="flex-1 px-3 py-1.5 text-xs font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50"
                >
                  Editar
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDelete(doc.id);
                  }}
                  className="px-3 py-1.5 text-xs font-medium text-red-600 border border-red-300 rounded-lg hover:bg-red-50"
                >
                  Excluir
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pagination info */}
      {!loadingDocs && total > documentos.length && (
        <p className="text-center text-sm text-[var(--ink-secondary)]">
          Mostrando {documentos.length} de {total} documentos
        </p>
      )}

      {/* Create Modal */}
      <CreateDocumentoModal
        open={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={fetchDocumentos}
      />
    </div>
  );
}
