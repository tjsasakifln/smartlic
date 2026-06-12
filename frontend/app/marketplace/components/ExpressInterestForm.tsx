"use client";

import { useState } from "react";
import { Button } from "@/app/components/ui/button";

interface ExpressInterestFormProps {
  opportunityId: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function ExpressInterestForm({
  opportunityId,
  onClose,
  onSuccess,
}: ExpressInterestFormProps) {
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/v1/marketplace/express-interest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          opportunity_id: opportunityId,
          message: message.trim() || undefined,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Erro ${res.status}`);
      }

      onSuccess();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Erro ao registrar interesse");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
      data-testid="express-interest-modal"
    >
      <div
        className="w-full max-w-md rounded-xl bg-[var(--surface-1)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-4">
          Demonstrar Interesse
        </h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="interest-message"
              className="block text-sm font-medium text-[var(--text-primary)] mb-1"
            >
              Mensagem (opcional)
            </label>
            <textarea
              id="interest-message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="Explique por que você tem interesse e como pode contribuir..."
              className="w-full min-h-[100px] rounded-lg border border-[var(--border-primary)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-strong)] resize-none"
              maxLength={1000}
            />
            <p className="text-xs text-[var(--text-tertiary)] mt-1 text-right">
              {message.length}/1000
            </p>
          </div>

          {error && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 text-sm text-red-700">
              {error}
            </div>
          )}

          <div className="flex gap-3">
            <Button
              type="button"
              variant="secondary"
              className="flex-1"
              onClick={onClose}
              disabled={loading}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              variant="primary"
              className="flex-1"
              disabled={loading}
              data-testid="submit-interest-btn"
            >
              {loading ? "Enviando..." : "Confirmar Interesse"}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
