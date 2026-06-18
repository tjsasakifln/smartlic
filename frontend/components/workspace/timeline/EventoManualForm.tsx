"use client";

import { useState } from "react";

interface EventoManualFormProps {
  editalId: string;
  onCreated: () => void;
}

export function EventoManualForm({ editalId, onCreated }: EventoManualFormProps) {
  const [tipo, setTipo] = useState<"nota_manual" | "lembrete">("nota_manual");
  const [titulo, setTitulo] = useState("");
  const [descricao, setDescricao] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!titulo.trim()) {
      setError("O titulo e obrigatorio.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch(`/api/workspace/timeline/${editalId}/evento`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tipo, titulo: titulo.trim(), descricao: descricao.trim() || undefined }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.message || "Erro ao criar evento.");
      }

      setTitulo("");
      setDescricao("");
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar evento.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="p-4 rounded-xl border border-[var(--border)] bg-[var(--surface-1)] space-y-3"
    >
      <h3 className="text-sm font-semibold text-[var(--ink)]">
        Adicionar evento
      </h3>

      {/* Tipo selector */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setTipo("nota_manual")}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
            tipo === "nota_manual"
              ? "bg-gray-800 text-white"
              : "bg-[var(--surface-2)] text-[var(--ink-secondary)]"
          }`}
        >
          Nota
        </button>
        <button
          type="button"
          onClick={() => setTipo("lembrete")}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
            tipo === "lembrete"
              ? "bg-orange-600 text-white"
              : "bg-[var(--surface-2)] text-[var(--ink-secondary)]"
          }`}
        >
          Lembrete
        </button>
      </div>

      {/* Titulo */}
      <input
        type="text"
        value={titulo}
        onChange={(e) => setTitulo(e.target.value)}
        placeholder="Titulo do evento"
        maxLength={500}
        className="w-full px-3 py-2 text-sm border rounded-lg bg-white text-[var(--ink)] placeholder:text-[var(--ink-tertiary)]"
      />

      {/* Descricao */}
      <textarea
        value={descricao}
        onChange={(e) => setDescricao(e.target.value)}
        placeholder="Descricao (opcional)"
        maxLength={5000}
        rows={3}
        className="w-full px-3 py-2 text-sm border rounded-lg bg-white text-[var(--ink)] placeholder:text-[var(--ink-tertiary)] resize-none"
      />

      {error && (
        <p className="text-xs text-red-600">{error}</p>
      )}

      <button
        type="submit"
        disabled={submitting || !titulo.trim()}
        className="w-full px-4 py-2 text-sm font-medium text-white bg-[var(--brand-blue)] rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
      >
        {submitting ? "Salvando..." : "Adicionar"}
      </button>
    </form>
  );
}
