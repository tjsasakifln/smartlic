"use client";

/**
 * CONSULT-001 (#1613): Consultant Clientes — Main page for managing
 * clients in the Consultoria plan (R$997/mes).
 *
 * Features:
 * - List active/revoked clients
 * - Invite new clients via email
 * - Share resources with clients
 * - Revoke client access
 */

import React, { useEffect, useState, useCallback } from "react";
import ClientInviteModal from "./components/ClientInviteModal";
import ClientList, { Client } from "./components/ClientList";
import ShareWithClient from "./components/ShareWithClient";

const API_BASE = "/api";

export default function ConsultoriaClientesPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [shareTarget, setShareTarget] = useState<{
    id: string;
    email?: string;
  } | null>(null);

  const fetchClients = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/v1/consultoria/clients`);
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(
          errBody.detail || `Erro ao carregar clientes (${resp.status})`,
        );
      }
      const data = await resp.json();
      setClients(data.clients || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao carregar dados.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  const handleInvite = async (email: string) => {
    const resp = await fetch(`${API_BASE}/v1/consultoria/invite-client`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_email: email }),
    });
    if (!resp.ok) {
      const errBody = await resp.json().catch(() => ({}));
      throw new Error(errBody.detail || "Erro ao enviar convite.");
    }
    await fetchClients();
  };

  const handleRevoke = async (clientId: string) => {
    const confirmed = window.confirm(
      "Tem certeza que deseja revogar o acesso deste cliente?",
    );
    if (!confirmed) return;

    try {
      const resp = await fetch(
        `${API_BASE}/v1/consultoria/clients/${clientId}`,
        { method: "DELETE" },
      );
      if (!resp.ok) {
        const errBody = await resp.json().catch(() => ({}));
        throw new Error(errBody.detail || "Erro ao revogar acesso.");
      }
      await fetchClients();
    } catch (err) {
      alert(err instanceof Error ? err.message : "Erro ao revogar acesso.");
    }
  };

  const handleShare = async (
    clientId: string,
    resourceType: string,
    resourceId: string,
  ) => {
    const resp = await fetch(
      `${API_BASE}/v1/consultoria/share/${clientId}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resource_type: resourceType, resource_id: resourceId }),
      },
    );
    if (!resp.ok) {
      const errBody = await resp.json().catch(() => ({}));
      throw new Error(errBody.detail || "Erro ao compartilhar.");
    }
  };

  const activeCount = clients.filter((c) => c.status === "active").length;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">
          Gestão de Clientes
        </h1>
        <p className="mt-1 text-sm text-gray-500">
          Plano Consultoria &mdash; Gerencie seus clientes e compartilhe
          análises.
        </p>
      </div>

      {/* Stats */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs text-gray-500">Total de Clientes</p>
          <p className="mt-1 text-2xl font-bold text-gray-900">
            {clients.length}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs text-gray-500">Ativos</p>
          <p className="mt-1 text-2xl font-bold text-green-600">
            {activeCount}
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <p className="text-xs text-gray-500">Limite</p>
          <p className="mt-1 text-2xl font-bold text-gray-400">10</p>
        </div>
      </div>

      {/* Actions */}
      <div className="mb-6">
        <button
          onClick={() => setShowInviteModal(true)}
          className="rounded-md bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700"
        >
          + Convidar Cliente
        </button>
      </div>

      {/* Error state */}
      {error && (
        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
          <button
            onClick={fetchClients}
            className="mt-2 text-sm font-medium text-red-600 hover:text-red-800"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {/* Client list */}
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
        <ClientList
          clients={clients}
          loading={loading}
          onRevoke={handleRevoke}
          onShare={(clientId) => {
            const client = clients.find(
              (c) => c.client_id === clientId || c.id === clientId,
            );
            setShareTarget({
              id: clientId,
              email: client?.client_email,
            });
          }}
        />
      </div>

      {/* Modals */}
      <ClientInviteModal
        isOpen={showInviteModal}
        onClose={() => setShowInviteModal(false)}
        onInvite={handleInvite}
      />

      <ShareWithClient
        clientId={shareTarget?.id || ""}
        clientEmail={shareTarget?.email}
        isOpen={!!shareTarget}
        onClose={() => setShareTarget(null)}
        onShare={handleShare}
      />
    </div>
  );
}
