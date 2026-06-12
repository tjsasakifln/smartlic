"use client";

import React from "react";

interface Client { id: string; consultant_id: string; client_id: string | null; client_email: string | null; status: string; created_at: string; }
interface Props { clients: Client[]; onRevoke: (id: string) => void; loading: boolean; }

export default function ClientList({ clients, onRevoke, loading }: Props) {
  if (!loading && clients.length === 0) return (<div className="text-center py-16"><div className="text-4xl mb-3">{String.fromCodePoint(0x1F465)}</div><h3 className="text-lg font-medium text-gray-900 mb-1">Nenhum cliente ainda</h3><p className="text-sm text-gray-500">Convide seu primeiro cliente.</p></div>);

  const activeClients = clients.filter(c => c.status === "active");
  const revokedClients = clients.filter(c => c.status === "revoked");

  const renderRow = (client: Client) => (
    <div key={client.id} className={`flex items-center justify-between p-4 rounded-lg border ${client.status === "active" ? "bg-white border-gray-200" : "bg-gray-50 border-gray-200 opacity-60"}`}>
      <div className="flex items-center gap-4">
        <div className={`w-2.5 h-2.5 rounded-full ${client.status === "active" ? "bg-emerald-500" : "bg-gray-400"}`} />
        <div><p className="text-sm font-medium text-gray-900">{client.client_email || client.client_id || "Pendente"}</p><p className="text-xs text-gray-400">{client.status === "active" ? "Ativo" : "Revogado"} &middot; {new Date(client.created_at).toLocaleDateString("pt-BR")}</p></div>
      </div>
      <div>{client.status === "active" && <button onClick={() => { if (confirm("Revogar acesso?")) onRevoke(client.id); }} className="px-3 py-1.5 text-xs font-medium text-red-600 bg-red-50 border border-red-200 rounded-md hover:bg-red-100">Revogar</button>}{client.status === "revoked" && <span className="text-xs text-gray-400 italic">Acesso revogado</span>}</div>
    </div>
  );

  return (<div className="space-y-4">
    {activeClients.length > 0 && <div><h3 className="text-sm font-medium text-gray-500 mb-2">Ativos ({activeClients.length})</h3><div className="space-y-2">{activeClients.map(renderRow)}</div></div>}
    {revokedClients.length > 0 && <div className="mt-6"><h3 className="text-sm font-medium text-gray-400 mb-2">Revogados ({revokedClients.length})</h3><div className="space-y-2">{revokedClients.map(renderRow)}</div></div>}
  </div>);
}
