"use client";

/**
 * REPORT-MONTHLY-001 (#1620): Monthly Report landing page.
 *
 * Features:
 * - Sector selector for preview
 * - Report preview with key metrics, top opportunities, top winners
 * - Subscribe button (R$97/mes)
 * - List of active subscriptions
 */

import React, { useEffect, useState, useCallback } from "react";
import ReportPreview from "./components/ReportPreview";
import SubscribeButton from "./components/SubscribeButton";
import SubscriptionList from "./components/SubscriptionList";

const API_BASE = "/api";
const SECTORS = [
  { id: "alimentos", name: "Alimentos" },
  { id: "engenharia", name: "Engenharia" },
  { id: "limpeza", name: "Limpeza e Conservacao" },
  { id: "vigilancia", name: "Vigilancia" },
  { id: "informatica", name: "Informatica" },
  { id: "medicamentos", name: "Medicamentos" },
];

export default function RelatoriosMensalPage() {
  const [selectedSector, setSelectedSector] = useState("alimentos");
  const [previewData, setPreviewData] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [subscriptions, setSubscriptions] = useState<any[]>([]);
  const [subsLoading, setSubsLoading] = useState(false);

  const fetchPreview = useCallback(async (sector: string) => {
    setPreviewLoading(true);
    setPreviewError(null);
    try {
      const resp = await fetch(
        `${API_BASE}/v1/report-mensal/preview/${sector}`,
      );
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(
          errBody.detail || `Erro ao carregar preview (${resp.status})`,
        );
      }
      setPreviewData(await resp.json());
    } catch (err) {
      setPreviewError(
        err instanceof Error ? err.message : "Erro ao carregar preview.",
      );
    } finally {
      setPreviewLoading(false);
    }
  }, []);

  const fetchSubscriptions = useCallback(async () => {
    setSubsLoading(true);
    try {
      const resp = await fetch(
        `${API_BASE}/v1/report-mensal/subscriptions`,
      );
      if (resp.ok) {
        const data = await resp.json();
        setSubscriptions(data.subscriptions || []);
      }
    } catch {
      // Silently fail
    } finally {
      setSubsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPreview(selectedSector);
  }, [selectedSector, fetchPreview]);

  useEffect(() => {
    fetchSubscriptions();
  }, [fetchSubscriptions]);

  const handleSubscribe = async (sectorId: string) => {
    const resp = await fetch(`${API_BASE}/v1/report-mensal/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sector_id: sectorId }),
    });
    if (!resp.ok) {
      const errBody = await resp.json().catch(() => ({}));
      throw new Error(errBody.detail || "Erro ao assinar.");
    }
    await fetchSubscriptions();
  };

  const handleCancel = async (subId: string) => {
    const confirmed = window.confirm(
      "Tem certeza que deseja cancelar esta assinatura?",
    );
    if (!confirmed) return;

    try {
      const resp = await fetch(
        `${API_BASE}/v1/report-mensal/cancel/${subId}`,
        { method: "POST" },
      );
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(errBody.detail || "Erro ao cancelar.");
      }
      await fetchSubscriptions();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao cancelar.");
    }
  };

  const selectedSectorName =
    SECTORS.find((s) => s.id === selectedSector)?.name || selectedSector;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Panorama Mensal de Licitacoes
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Relatorio executivo mensal do seu setor — R$ 97/mes
        </p>
      </div>

      {/* Sector Selector */}
      <div className="mb-6">
        <label className="block text-sm font-medium text-gray-700">
          Selecione o setor
        </label>
        <select
          value={selectedSector}
          onChange={(e) => setSelectedSector(e.target.value)}
          className="mt-1 block w-full max-w-xs rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm focus:border-green-500 focus:outline-none focus:ring-1 focus:ring-green-500"
        >
          {SECTORS.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {/* Preview */}
      {previewError ? (
        <div className="mb-6 rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{previewError}</p>
          <button
            onClick={() => fetchPreview(selectedSector)}
            className="mt-2 text-sm font-medium text-red-600 hover:text-red-800"
          >
            Tentar novamente
          </button>
        </div>
      ) : (
        <div className="mb-8">
          <ReportPreview
            sectorId={selectedSector}
            sectorName={selectedSectorName}
            period={previewData?.period || ""}
            totalLicitacoes={previewData?.total_licitacoes || 0}
            totalValue={previewData?.total_value || 0}
            avgValue={previewData?.avg_value || 0}
            topOpportunities={previewData?.top_opportunities || []}
            topWinners={previewData?.top_winners || []}
            executiveSummary={
              previewData?.executive_summary || "Carregando preview..."
            }
            loading={previewLoading}
          />
        </div>
      )}

      {/* Subscribe CTA */}
      <div className="mb-8">
        <SubscribeButton
          sectorId={selectedSector}
          sectorName={selectedSectorName}
          onSubscribe={handleSubscribe}
        />
      </div>

      {/* My Subscriptions */}
      <section className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">
          Minhas Assinaturas
        </h2>
        <SubscriptionList
          subscriptions={subscriptions}
          loading={subsLoading}
          onCancel={handleCancel}
        />
      </section>
    </div>
  );
}
