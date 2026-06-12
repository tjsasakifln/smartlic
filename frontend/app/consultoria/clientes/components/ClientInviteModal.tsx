"use client";

import React, { useState } from "react";

interface Props { onClose: () => void; onInvite: (email: string) => Promise<void>; }

export default function ClientInviteModal({ onClose, onInvite }: Props) {
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!email.trim()) { setError("Informe o email."); return; }
    if (!/\S+@\S+\.\S+/.test(email)) { setError("Email invalido."); return; }
    try { setSending(true); await onInvite(email.trim()); }
    catch { setError("Erro ao gerar convite."); }
    finally { setSending(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Convidar Cliente</h2>
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">Email do Cliente</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="cliente@exemplo.com" className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" autoFocus />
          </div>
          {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">{error}</div>}
          <div className="flex items-center justify-end gap-3">
            <button type="button" onClick={onClose} disabled={sending} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800">Cancelar</button>
            <button type="submit" disabled={sending} className={`px-4 py-2 rounded-lg text-sm font-medium text-white ${sending ? "bg-emerald-400 cursor-not-allowed" : "bg-emerald-600 hover:bg-emerald-700"}`}>{sending ? "Gerando..." : "Gerar Link de Convite"}</button>
          </div>
        </form>
        <p className="mt-4 text-xs text-gray-400">Link expira em 7 dias. Cliente cria conta gratuita sem cartao.</p>
      </div>
    </div>
  );
}
