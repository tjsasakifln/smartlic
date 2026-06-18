"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "../../../components/AuthProvider";
import { AuthLoadingScreen } from "../../../components/AuthLoadingScreen";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DocumentoData {
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

// ---------------------------------------------------------------------------
// Editor Page
// ---------------------------------------------------------------------------

export default function DocumentoEditorPage() {
  const params = useParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();
  const documentoId = params.id as string | undefined;

  if (!documentoId) {
    return <div className="max-w-4xl mx-auto px-4 py-8 text-center text-red-600">ID do documento nao encontrado.</div>;
  }

  const [documento, setDocumento] = useState<DocumentoData | null>(null);
  const [titulo, setTitulo] = useState("");
  const [conteudo, setConteudo] = useState("");
  const [editalId, setEditalId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [rendering, setRendering] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveFeedback, setSaveFeedback] = useState<string | null>(null);

  // Fetch document
  const fetchDocumento = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const res = await fetch(`/api/workspace/documentos/${documentoId}`);
      if (!res.ok) {
        if (res.status === 404) {
          router.replace("/workspace/documentos");
          return;
        }
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || data.detail || "Erro ao carregar documento");
      }

      const data: DocumentoData = await res.json();
      setDocumento(data);
      setTitulo(data.titulo);
      setConteudo(data.conteudo);
      setEditalId(data.edital_id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar documento");
    } finally {
      setLoading(false);
    }
  }, [documentoId, router]);

  useEffect(() => {
    if (session && documentoId) fetchDocumento();
  }, [session, documentoId, fetchDocumento]);

  // Save document
  const handleSave = useCallback(async () => {
    setSaving(true);
    setSaveFeedback(null);

    try {
      const body: Record<string, string> = {};
      if (titulo !== documento?.titulo) body.titulo = titulo;
      if (conteudo !== documento?.conteudo) body.conteudo = conteudo;

      if (Object.keys(body).length === 0) {
        setSaveFeedback("Nenhuma alteracao para salvar.");
        setSaving(false);
        return;
      }

      const res = await fetch(`/api/workspace/documentos/${documentoId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || data.detail || "Erro ao salvar");
      }

      const updated: DocumentoData = await res.json();
      setDocumento(updated);
      setSaveFeedback("Salvo com sucesso!");
      setTimeout(() => setSaveFeedback(null), 3000);
    } catch (err) {
      setSaveFeedback(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }, [documentoId, titulo, conteudo, documento]);

  // Render variables
  const handleRender = useCallback(async () => {
    if (!editalId.trim()) {
      alert("Informe o ID do edital para renderizar as variaveis.");
      return;
    }

    setRendering(true);

    try {
      const res = await fetch(`/api/workspace/documentos/${documentoId}/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ edital_id: editalId.trim() }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || data.detail || "Erro ao renderizar");
      }

      const updated: DocumentoData = await res.json();
      setDocumento(updated);
      setConteudo(updated.conteudo);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao renderizar variaveis");
    } finally {
      setRendering(false);
    }
  }, [documentoId, editalId]);

  const hasChanges = titulo !== documento?.titulo || conteudo !== documento?.conteudo;

  if (authLoading) return <AuthLoadingScreen />;

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 text-center text-[var(--ink-secondary)]">
        Carregando documento...
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
          <button onClick={fetchDocumento} className="ml-3 underline hover:no-underline">
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8 space-y-6">
      {/* Navigation */}
      <button
        onClick={() => router.push("/workspace/documentos")}
        className="text-sm text-blue-600 hover:underline"
      >
        &larr; Voltar para Documentos
      </button>

      {/* Title */}
      <input
        type="text"
        value={titulo}
        onChange={(e) => setTitulo(e.target.value)}
        className="w-full text-2xl font-display font-semibold text-[var(--ink)] bg-transparent border-b border-gray-200 focus:border-blue-500 focus:outline-none pb-1"
        placeholder="Titulo do documento"
      />

      {/* Meta info */}
      <div className="flex flex-wrap items-center gap-3 text-sm text-[var(--ink-secondary)]">
        <span>
          Tipo: <strong>{documento?.tipo}</strong>
        </span>

        {/* Edital ID for render */}
        <div className="flex items-center gap-2 ml-auto">
          <label className="text-xs">ID do Edital:</label>
          <input
            type="text"
            value={editalId}
            onChange={(e) => setEditalId(e.target.value)}
            className="px-2 py-1 text-xs border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-blue-500 w-48"
            placeholder="ID do edital para variaveis"
          />
          <button
            onClick={handleRender}
            disabled={rendering}
            className="px-3 py-1 text-xs font-medium text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50 disabled:opacity-50"
          >
            {rendering ? "Renderizando..." : "Renderizar Variaveis"}
          </button>
        </div>
      </div>

      {/* Editor */}
      <textarea
        value={conteudo}
        onChange={(e) => setConteudo(e.target.value)}
        className="w-full h-[60vh] px-4 py-3 font-mono text-sm leading-relaxed border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-y"
        placeholder="Digite o conteudo do documento aqui... Use {{variavel}} para marcadores."
      />

      {/* Save bar */}
      <div className="flex items-center justify-between sticky bottom-0 bg-white py-3 border-t border-gray-100">
        <div>
          {saveFeedback && (
            <span
              className={`text-sm ${
                saveFeedback === "Salvo com sucesso!"
                  ? "text-green-600"
                  : "text-red-600"
              }`}
            >
              {saveFeedback}
            </span>
          )}
        </div>

        <div className="flex gap-3">
          <button
            onClick={() => router.push("/workspace/documentos")}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200"
          >
            Voltar
          </button>
          <button
            onClick={handleSave}
            disabled={saving || !hasChanges}
            className="px-6 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {saving ? "Salvando..." : "Salvar"}
          </button>
        </div>
      </div>

      {/* Helper info */}
      <details className="text-sm text-[var(--ink-secondary)] border border-gray-200 rounded-lg p-3">
        <summary className="cursor-pointer font-medium">Variaveis disponiveis</summary>
        <div className="mt-2 space-y-1">
          <p><code>{`{{objeto}}`}</code> — Objeto do edital</p>
          <p><code>{`{{orgao}}`}</code> — Orgao publicador</p>
          <p><code>{`{{valor}}`}</code> — Valor estimado</p>
          <p><code>{`{{data_abertura}}`}</code> — Data de abertura</p>
          <p><code>{`{{modalidade}}`}</code> — Modalidade da licitacao</p>
          <p><code>{`{{uf}}`}</code> — UF do orgao</p>
          <p><code>{`{{empresa}}`}</code> — Nome da sua empresa</p>
          <p><code>{`{{cnpj}}`}</code> — CNPJ da sua empresa</p>
          <p className="mt-2 text-xs text-gray-400">
            Clique em &quot;Renderizar Variaveis&quot; para substituir os marcadores pelos valores reais do edital e seu perfil.
          </p>
        </div>
      </details>
    </div>
  );
}
