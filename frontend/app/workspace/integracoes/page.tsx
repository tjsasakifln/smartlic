"use client";

import { useCallback, useEffect, useState } from "react";
import { Button } from "../../../components/ui/button";
import { Input } from "../../../components/ui/Input";
import { PageHeader } from "../../../components/PageHeader";
import { ErrorStateWithRetry } from "../../../components/ErrorStateWithRetry";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CanalIntegracao {
  id: string;
  user_id: string;
  tipo: "slack" | "teams" | "email";
  nome: string;
  url: string | null;
  email_destino: string | null;
  eventos: string[];
  ativo: boolean;
  created_at: string;
  updated_at: string;
}

interface CanalForm {
  tipo: "slack" | "teams" | "email";
  nome: string;
  url: string;
  email_destino: string;
  eventos: string[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function canalIcon(tipo: string): string {
  switch (tipo) {
    case "slack":
      return "#";
    case "teams":
      return "#";
    case "email":
      return "@";
    default:
      return "?";
  }
}

function canalLabel(tipo: string): string {
  switch (tipo) {
    case "slack":
      return "Slack";
    case "teams":
      return "Microsoft Teams";
    case "email":
      return "E-mail";
    default:
      return tipo;
  }
}

const EVENTOS_DISPONIVEIS = [
  { value: "alerta", label: "Alertas de novos editais" },
  { value: "timeline", label: "Atualizacoes de timeline" },
  { value: "resumo_diario", label: "Resumo diario" },
];

const FORM_INITIAL: CanalForm = {
  tipo: "slack",
  nome: "",
  url: "",
  email_destino: "",
  eventos: [],
};

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function IntegracoesPage() {
  const [canais, setCanais] = useState<CanalIntegracao[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<CanalForm>(FORM_INITIAL);
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);
  const [testMessage, setTestMessage] = useState<string | null>(null);

  // -------------------------------------------------------------------------
  // Fetch channels
  // -------------------------------------------------------------------------

  const fetchCanais = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/workspace/integracoes/canais");
      if (!res.ok) {
        throw new Error("Erro ao carregar canais");
      }
      const data: CanalIntegracao[] = await res.json();
      setCanais(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchCanais();
  }, [fetchCanais]);

  // -------------------------------------------------------------------------
  // Create channel
  // -------------------------------------------------------------------------

  const handleCreate = async () => {
    if (!form.nome.trim()) return;

    setSaving(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        tipo: form.tipo,
        nome: form.nome.trim(),
        eventos: form.eventos,
      };
      if (form.tipo === "email") {
        body.email_destino = form.email_destino.trim();
      } else {
        body.url = form.url.trim();
      }

      const res = await fetch("/api/workspace/integracoes/canais", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.message || "Erro ao criar canal");
      }

      setShowForm(false);
      setForm(FORM_INITIAL);
      await fetchCanais();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar canal");
    } finally {
      setSaving(false);
    }
  };

  // -------------------------------------------------------------------------
  // Delete channel
  // -------------------------------------------------------------------------

  const handleDelete = async (id: string) => {
    if (!confirm("Tem certeza que deseja remover este canal?")) return;

    try {
      const res = await fetch(`/api/workspace/integracoes/canais/${id}`, {
        method: "DELETE",
      });

      if (!res.ok && res.status !== 204) {
        throw new Error("Erro ao remover canal");
      }

      setCanais((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao remover canal");
    }
  };

  // -------------------------------------------------------------------------
  // Test channel
  // -------------------------------------------------------------------------

  const handleTest = async (id: string) => {
    setTestingId(id);
    setTestMessage(null);
    try {
      const res = await fetch(`/api/workspace/integracoes/test/${id}`, {
        method: "POST",
      });
      const data = await res.json();
      setTestMessage(data.mensagem || (data.sucesso ? "Enviado com sucesso" : "Falha ao enviar"));
    } catch (err) {
      setTestMessage("Erro ao enviar notificacao de teste");
    } finally {
      setTestingId(null);
    }
  };

  // -------------------------------------------------------------------------
  // Toggle event
  // -------------------------------------------------------------------------

  const toggleEvento = (value: string) => {
    setForm((prev) => ({
      ...prev,
      eventos: prev.eventos.includes(value)
        ? prev.eventos.filter((e) => e !== value)
        : [...prev.eventos, value],
    }));
  };

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <>
      <PageHeader title="Integracoes" />
      <div className="max-w-4xl mx-auto px-4 py-8">
        <p className="text-sm text-[var(--text-secondary)] mb-6">
          Conecte seu workspace a canais de notificacao
        </p>

      {/* Test message toast */}
      {testMessage && (
        <div className="mb-4 p-3 rounded-lg bg-[var(--accent-1)] border border-[var(--accent-2)] text-sm">
          {testMessage}
          <button
            className="ml-2 text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            onClick={() => setTestMessage(null)}
          >
            OK
          </button>
        </div>
      )}

      {error && (
        <div className="mb-4">
          <ErrorStateWithRetry message={error} onRetry={fetchCanais} />
        </div>
      )}

      {/* Header actions */}
      <div className="flex justify-end mb-6">
        <Button onClick={() => setShowForm((prev) => !prev)}>
          {showForm ? "Cancelar" : "Adicionar Canal"}
        </Button>
      </div>

      {/* Inline form */}
      {showForm && (
        <div className="mb-8 p-6 rounded-xl border border-[var(--border-1)] bg-[var(--surface-1)]">
          <h3 className="text-lg font-semibold mb-4">Novo Canal</h3>

          <div className="space-y-4">
            {/* Tipo */}
            <div>
              <label className="block text-sm font-medium mb-1">Tipo</label>
              <select
                className="w-full rounded-lg border border-[var(--border-1)] bg-[var(--bg-primary)] px-3 py-2 text-sm"
                value={form.tipo}
                onChange={(e) =>
                  setForm((prev) => ({
                    ...prev,
                    tipo: e.target.value as CanalForm["tipo"],
                  }))
                }
              >
                <option value="slack">Slack</option>
                <option value="teams">Microsoft Teams</option>
                <option value="email">E-mail</option>
              </select>
            </div>

            {/* Nome */}
            <div>
              <label className="block text-sm font-medium mb-1">Nome do Canal</label>
              <Input
                placeholder="Ex: Alertas de Editais"
                value={form.nome}
                onChange={(e) => setForm((prev) => ({ ...prev, nome: e.target.value }))}
              />
            </div>

            {/* URL (Slack/Teams) */}
            {form.tipo !== "email" && (
              <div>
                <label className="block text-sm font-medium mb-1">URL do Webhook</label>
                <Input
                  placeholder="https://hooks.slack.com/services/..."
                  value={form.url}
                  onChange={(e) => setForm((prev) => ({ ...prev, url: e.target.value }))}
                />
              </div>
            )}

            {/* Email destino */}
            {form.tipo === "email" && (
              <div>
                <label className="block text-sm font-medium mb-1">Email de Destino</label>
                <Input
                  type="email"
                  placeholder="email@exemplo.com"
                  value={form.email_destino}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, email_destino: e.target.value }))
                  }
                />
              </div>
            )}

            {/* Eventos */}
            <div>
              <label className="block text-sm font-medium mb-2">Eventos para notificar</label>
              <div className="space-y-2">
                {EVENTOS_DISPONIVEIS.map((evt) => (
                  <label key={evt.value} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={form.eventos.includes(evt.value)}
                      onChange={() => toggleEvento(evt.value)}
                      className="rounded border-[var(--border-1)]"
                    />
                    <span className="text-sm">{evt.label}</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="flex gap-3 pt-2">
              <Button onClick={handleCreate} disabled={saving || !form.nome.trim()}>
                {saving ? "Salvando..." : "Salvar"}
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setShowForm(false);
                  setForm(FORM_INITIAL);
                }}
              >
                Cancelar
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Channels list */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-24 rounded-xl bg-[var(--surface-1)] animate-pulse"
            />
          ))}
        </div>
      ) : canais.length === 0 ? (
        <div className="text-center py-16 px-4">
          <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-3">
            Nenhum canal configurado
          </h2>
          <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto">
            Adicione um canal Slack, Teams ou Email para comecar a receber notificacoes.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {canais.map((canal) => (
            <div
              key={canal.id}
              className="p-5 rounded-xl border border-[var(--border-1)] bg-[var(--surface-1)]"
            >
              <div className="flex items-start justify-between">
                <div className="flex items-start gap-4">
                  {/* Icon */}
                  <div className="w-10 h-10 rounded-lg bg-[var(--accent-1)] flex items-center justify-center text-lg font-bold text-[var(--accent-2)]">
                    {canalIcon(canal.tipo)}
                  </div>

                  {/* Info */}
                  <div>
                    <h3 className="font-semibold">{canal.nome}</h3>
                    <p className="text-sm text-[var(--text-secondary)]">
                      {canalLabel(canal.tipo)}
                    </p>
                    {canal.url && (
                      <p className="text-xs text-[var(--text-tertiary)] mt-1 truncate max-w-md">
                        {canal.url}
                      </p>
                    )}
                    {canal.email_destino && (
                      <p className="text-xs text-[var(--text-tertiary)] mt-1">
                        {canal.email_destino}
                      </p>
                    )}
                    {canal.eventos.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-2">
                        {canal.eventos.map((evt) => (
                          <span
                            key={evt}
                            className="px-2 py-0.5 text-xs rounded-full bg-[var(--accent-1)] text-[var(--accent-2)]"
                          >
                            {evt}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={testingId === canal.id}
                    onClick={() => handleTest(canal.id)}
                  >
                    {testingId === canal.id ? "Enviando..." : "Testar"}
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="text-red-500 hover:bg-red-50"
                    onClick={() => handleDelete(canal.id)}
                  >
                    Remover
                  </Button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      </div>
    </>
  );
}
