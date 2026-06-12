"use client";

/**
 * CONSULT-001 (#1613): ClientList — Table listing consultant's clients
 * with status and revoke action.
 */

import React from "react";

export interface Client {
  id: string;
  client_id?: string;
  client_email?: string;
  status: "active" | "revoked";
  created_at: string;
}

interface ClientListProps {
  clients: Client[];
  loading: boolean;
  onRevoke: (clientId: string) => void;
  onShare: (clientId: string) => void;
}

export default function ClientList({
  clients,
  loading,
  onRevoke,
  onShare,
}: ClientListProps) {
  if (loading) {
    return (
      <div className="py-8 text-center text-gray-500">
        Carregando clientes...
      </div>
    );
  }

  if (clients.length === 0) {
    return (
      <div className="py-8 text-center text-gray-500">
        Nenhum cliente encontrado. Convide seu primeiro cliente!
      </div>
    );
  }

  const statusBadge = (status: string) => {
    const isActive = status === "active";
    return (
      <span
        className={`inline-flex rounded-full px-2 py-0.5 text-xs font-medium ${
          isActive
            ? "bg-green-100 text-green-800"
            : "bg-gray-100 text-gray-600"
        }`}
      >
        {isActive ? "Ativo" : "Revogado"}
      </span>
    );
  };

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("pt-BR");
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Cliente
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Status
            </th>
            <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500">
              Desde
            </th>
            <th className="px-4 py-3 text-right text-xs font-medium uppercase tracking-wider text-gray-500">
              Ações
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {clients.map((client) => (
            <tr key={client.id} className="hover:bg-gray-50">
              <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-900">
                {client.client_email || "---"}
              </td>
              <td className="whitespace-nowrap px-4 py-3">
                {statusBadge(client.status)}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-sm text-gray-500">
                {formatDate(client.created_at)}
              </td>
              <td className="whitespace-nowrap px-4 py-3 text-right text-sm">
                {client.status === "active" && (
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => onShare(client.client_id || client.id)}
                      className="text-green-600 hover:text-green-800"
                    >
                      Compartilhar
                    </button>
                    <button
                      onClick={() => onRevoke(client.client_id || client.id)}
                      className="text-red-600 hover:text-red-800"
                    >
                      Revogar
                    </button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
