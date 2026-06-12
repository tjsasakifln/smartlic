"use client";

/**
 * REPORT-MONTHLY-001 (#1620): SubscribeButton — CTA button for subscribing
 * to the monthly sector report (R$97/mes).
 */

import React, { useState } from "react";

interface SubscribeButtonProps {
  sectorId: string;
  sectorName: string;
  onSubscribe: (sectorId: string) => Promise<void>;
}

export default function SubscribeButton({
  sectorId,
  sectorName,
  onSubscribe,
}: SubscribeButtonProps) {
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubscribe = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      await onSubscribe(sectorId);
      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Erro ao assinar relatorio.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-lg border border-green-200 bg-green-50 p-6 text-center">
      <h3 className="text-lg font-semibold text-green-900">
        Panorama Mensal — {sectorName}
      </h3>
      <p className="mt-2 text-sm text-green-700">
        Receba todo mes um relatorio executivo completo do setor de{" "}
        <strong>{sectorName}</strong> com analises, tendencias e previsoes.
      </p>
      <p className="mt-1 text-2xl font-bold text-green-600">
        R$ 97<span className="text-sm font-normal">/mes</span>
      </p>

      {success ? (
        <p className="mt-4 text-sm text-green-600">
          Inscricao realizada com sucesso! Voce recebera o relatorio no
          primeiro dia util do mes.
        </p>
      ) : (
        <button
          onClick={handleSubscribe}
          disabled={loading}
          className="mt-4 rounded-md bg-green-600 px-6 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
        >
          {loading ? "Assinando..." : "Assinar Agora"}
        </button>
      )}

      {error && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {error}
        </p>
      )}

      <p className="mt-3 text-xs text-gray-500">
        Cancele quando quiser. Sem fidelidade.
      </p>
    </div>
  );
}
