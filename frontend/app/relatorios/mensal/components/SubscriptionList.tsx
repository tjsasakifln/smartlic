"use client";

/**
 * REPORT-MONTHLY-001 (#1620): SubscriptionList — Shows user's active
 * monthly report subscriptions.
 */

import React from "react";

interface Subscription {
  id: string;
  sector_id: string;
  status: string;
  created_at: string;
}

interface SubscriptionListProps {
  subscriptions: Subscription[];
  loading: boolean;
  onCancel: (id: string) => void;
}

const SECTOR_NAMES: Record<string, string> = {
  alimentos: "Alimentos",
  engenharia: "Engenharia",
  limpeza: "Limpeza",
  vigilancia: "Vigilancia",
  informatica: "Informatica",
};

export default function SubscriptionList({
  subscriptions,
  loading,
  onCancel,
}: SubscriptionListProps) {
  if (loading) {
    return (
      <div className="py-4 text-sm text-gray-500">
        Carregando assinaturas...
      </div>
    );
  }

  if (subscriptions.length === 0) {
    return (
      <div className="py-4 text-sm text-gray-500">
        Voce ainda nao possui assinaturas de relatorios mensais.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {subscriptions.map((sub) => {
        const sectorName =
          SECTOR_NAMES[sub.sector_id] || sub.sector_id;
        const isActive = sub.status === "active";

        return (
          <div
            key={sub.id}
            className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4"
          >
            <div>
              <p className="font-medium text-gray-900">
                Panorama Mensal — {sectorName}
              </p>
              <p className="mt-0.5 text-xs text-gray-500">
                {isActive ? "Ativo" : "Cancelado"} |{" "}
                {new Date(sub.created_at).toLocaleDateString("pt-BR")}
              </p>
            </div>
            {isActive && (
              <button
                onClick={() => onCancel(sub.id)}
                className="rounded-md border border-red-200 px-3 py-1 text-xs text-red-600 hover:bg-red-50"
              >
                Cancelar
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
