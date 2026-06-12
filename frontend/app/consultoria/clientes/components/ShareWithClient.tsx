"use client";

import React, { useCallback, useEffect, useState } from "react";

interface Client { id: string; client_email: string | null; status: string; }
interface Props { resourceType: "busca" | "pipeline" | "analise"; resourceId: string; onShareComplete?: (clientId: string) => void; }

export default function ShareWithClient({ resourceType, resourceId, onShareComplete }: Props) {
  const [open, setOpen] = useState(false);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(false);
  const [sharing, setSharing] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: string; text: string } | null>(null);

  const fetchClients = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/consultoria/clients");
      if (!res.ok) return;
      const data = await res.json();
      setClients((Array.isArray(data) ? data : data?.clients || []).filter((c: Client) => c.status === "active"));
    } catch { /* noop */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { if (open) fetchClients(); }, [open, fetchClients]);

  const handleShare = async (clientId: string) => {
    setSharing(clientId); setMessage(null);
    try {
      const res = await fetch(`/api/consultoria/share/${clientId}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resource_type: resourceType, resource_id: resourceId }) });
      if (!res.ok) { const d = await res.json(); setMessage({ type: "error", text: d?.detail || "Erro." }); return; }
      setMessage({ type: "success", text: "Compartilhado!" }); onShareComplete?.(clientId);
    } catch { setMessage({ type: "error", text: "Erro de conexao." }); }
    finally { setSharing(null); }
  };

  const labels: Record<string, string> = { busca: "Busca", pipeline: "Pipeline", analise: "Analise" };

  return (<div className="relative">
    <button onClick={() => setOpen(!open)} className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-300 rounded-md hover:bg-gray-50">Compartilhar</button>
    {open && <div className="absolute right-0 mt-2 w-72 bg-white border border-gray-200 rounded-xl shadow-lg z-50">
      <div className="p-3 border-b border-gray-100"><h4 className="text-sm font-medium">Compartilhar {labels[resourceType]}</h4><p className="text-xs text-gray-400">Selecione um cliente</p></div>
      <div className="max-h-60 overflow-y-auto p-2">
        {loading && <div className="text-center py-4"><div className="inline-block w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" /></div>}
        {!loading && clients.length === 0 && <div className="text-center py-6"><p className="text-sm text-gray-400">Nenhum cliente ativo</p></div>}
        {!loading && clients.map(c => <button key={c.id} onClick={() => handleShare(c.id)} disabled={sharing === c.id} className={`w-full text-left p-2.5 rounded-lg text-sm ${sharing === c.id ? "bg-gray-100 cursor-wait" : "hover:bg-gray-50"}`}>{c.client_email || "Cliente"}</button>)}
      </div>
      {message && <div className={`p-2.5 text-xs ${message.type === "success" ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>{message.text}</div>}
      <div className="p-2 border-t border-gray-100"><button onClick={() => { setOpen(false); setMessage(null); }} className="w-full py-1.5 text-xs text-gray-500 hover:text-gray-700">Fechar</button></div>
    </div>}
  </div>);
}
