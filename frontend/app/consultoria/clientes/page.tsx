"use client";

import React, { useCallback, useEffect, useState } from "react";
import ClientInviteModal from "./components/ClientInviteModal";
import ClientList from "./components/ClientList";

interface Client {
  id: string;
  consultant_id: string;
  client_id: string | null;
  client_email: string | null;
  status: string;
  created_at: string;
}

export default function ConsultoriaClientesPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const fetchClients = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch("/api/consultoria/clients");
      if (!res.ok) {
        if (res.status === 401) { setError("Autenticacao necessaria."); return; }
        if (res.status === 403) { setError("Exclusivo do plano Consultoria."); return; }
        const data = await res.json();
        setError(data?.message || "Erro ao carregar clientes.");
        return;
      }
      const data = await res.json();
      setClients(Array.isArray(data) ? data : data?.clients || []);
    } catch { setError("Erro de conexao."); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchClients(); }, [fetchClients]);

  const activeCount = clients.filter((c) => c.status === "active").length;
  const MAX_SEATS = 10;

  const handleInvite = async (email: string) => {
    setMessage(null);
    try {
      const res = await fetch("/api/consultoria/invite-client", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ client_email: email }) });
      const data = await res.json();
      if (!res.ok) { setMessage({ type: "error", text: data?.detail || data?.message || "Erro." }); return; }
      setMessage({ type: "success", text: "Convite gerado!" });
      setShowInviteModal(false);
      await fetchClients();
    } catch { setMessage({ type: "error", text: "Erro de conexao." }); }
  };

  const handleRevoke = async (clientId: string) => {
    setMessage(null);
    try {
      const res = await fetch(`/api/consultoria/clients/${clientId}`, { method: "DELETE" });
      const data = await res.json();
      if (!res.ok) { setMessage({ type: "error", text: data?.detail || "Erro." }); return; }
      setMessage({ type: "success", text: "Acesso revogado." });
      await fetchClients();
    } catch { setMessage({ type: "error", text: "Erro de conexao." }); }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Meus Clientes</h1>
            <p className="text-sm text-gray-500 mt-1">Gerencie assentos read-only do plano Consultoria</p>
          </div>
          <div className="text-right">
            <span className="text-sm text-gray-500">Assentos: <strong>{activeCount}</strong> / {MAX_SEATS}</span>
            <div className="w-48 h-2 bg-gray-200 rounded-full mt-1"><div className="h-2 bg-emerald-500 rounded-full transition-all" style={{ width: Math.min((activeCount / MAX_SEATS) * 100, 100) + "%" }} /></div>
          </div>
        </div>

        {message && (<div className={`mb-6 p-4 rounded-lg text-sm ${message.type === "success" ? "bg-emerald-50 text-emerald-700 border border-emerald-200" : "bg-red-50 text-red-700 border border-red-200"}`}>{message.text}</div>)}

        <div className="mb-6">
          <button onClick={() => setShowInviteModal(true)} disabled={activeCount >= MAX_SEATS} className={`px-6 py-2.5 rounded-lg text-sm font-medium transition-colors ${activeCount >= MAX_SEATS ? "bg-gray-300 text-gray-500 cursor-not-allowed" : "bg-emerald-600 text-white hover:bg-emerald-700"}`}>+ Convidar Cliente</button>
        </div>

        {loading && (<div className="text-center py-12"><div className="inline-block w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin" /><p className="text-sm text-gray-500 mt-2">Carregando...</p></div>)}
        {!loading && error && (<div className="text-center py-12"><div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md mx-auto"><p className="text-red-700 text-sm">{error}</p><button onClick={fetchClients} className="mt-4 text-sm text-red-600 underline">Tentar novamente</button></div></div>)}
        {!loading && !error && (<ClientList clients={clients} onRevoke={handleRevoke} loading={loading} />)}
        {showInviteModal && (<ClientInviteModal onClose={() => setShowInviteModal(false)} onInvite={handleInvite} />)}

        {!loading && !error && (<div className="mt-8 p-4 bg-blue-50 border border-blue-200 rounded-lg"><h3 className="text-sm font-medium text-blue-800">Sobre Assentos Consultoria</h3><ul className="mt-2 text-sm text-blue-600 space-y-1"><li>Cliente acessa com conta gratuita (sem trial, sem cartao)</li><li>Clientes veem APENAS itens compartilhados por voce</li><li>Clientes NAO editam pipeline, buscas ou exportam</li><li>Voce pode revogar acesso a qualquer momento</li><li>Limite de {MAX_SEATS} assentos ativos</li></ul></div>)}
      </div>
    </div>
  );
}
