"use client";

/**
 * CONSULT-001 (#1613): ShareWithClient — Dropdown/modal for sharing resources
 * (busca, pipeline, analise) with a specific client.
 */

import React, { useState } from "react";

interface ShareWithClientProps {
  clientId: string;
  clientEmail?: string;
  isOpen: boolean;
  onClose: () => void;
  onShare: (clientId: string, resourceType: string, resourceId: string) => Promise<void>;
}

const RESOURCE_TYPES = [
  { value: "busca", label: "Busca / Análise" },
  { value: "pipeline", label: "Pipeline / Kanban" },
  { value: "analise", label: "Análise Detalhada" },
];

export default function ShareWithClient({
  clientId,
  clientEmail,
  isOpen,
  onClose,
  onShare,
}: ShareWithClientProps) {
  const [resourceType, setResourceType] = useState("busca");
  const [resourceId, setResourceId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!resourceId.trim()) {
      setError("Informe o ID do recurso.");
      return;
    }

    setLoading(true);
    try {
      await onShare(clientId, resourceType, resourceId.trim());
      setSuccess("Recurso compartilhado com sucesso!");
      setResourceId("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erro ao compartilhar recurso.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">
            Compartilhar com{" "}
            {clientEmail ? (
              <span className="text-green-700">{clientEmail}</span>
            ) : (
              "cliente"
            )}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
            aria-label="Fechar"
          >
            &times;
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700">
              Tipo de recurso
            </label>
            <select
              value={resourceType}
              onChange={(e) => setResourceType(e.target.value)}
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
              disabled={loading}
            >
              {RESOURCE_TYPES.map((rt) => (
                <option key={rt.value} value={rt.value}>
                  {rt.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700">
              ID do recurso
            </label>
            <input
              type="text"
              value={resourceId}
              onChange={(e) => setResourceId(e.target.value)}
              placeholder="UUID do recurso"
              className="mt-1 block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
              disabled={loading}
              required
            />
          </div>

          {error && (
            <p className="text-sm text-red-600" role="alert">
              {error}
            </p>
          )}

          {success && (
            <p className="text-sm text-green-600" role="status">
              {success}
            </p>
          )}

          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
              disabled={loading}
            >
              Fechar
            </button>
            <button
              type="submit"
              className="rounded-md bg-green-600 px-4 py-2 text-sm text-white hover:bg-green-700 disabled:opacity-50"
              disabled={loading}
            >
              {loading ? "Compartilhando..." : "Compartilhar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
