"use client";

/**
 * RBAC-ORG-001 AC11 — 2-step confirm modal for transferring org ownership.
 *
 * Step 1: warning + acknowledgment checkbox.
 * Step 2: type the target member's email (or user-id fallback) verbatim.
 * Both gates must pass before the "Transferir agora" button enables.
 */

import { useId, useState, useEffect } from "react";
import type { OrgRole } from "./RoleControls";

interface Member {
  user_id: string;
  email?: string;
  role: OrgRole;
}

export interface TransferOwnershipModalProps {
  open: boolean;
  target: Member | null;
  /** Called with target on confirm. Parent issues the API call. */
  onConfirm: (target: Member) => Promise<void> | void;
  onCancel: () => void;
  /** True while the parent waits on the API. */
  busy?: boolean;
}

export default function TransferOwnershipModal({
  open,
  target,
  onConfirm,
  onCancel,
  busy = false,
}: TransferOwnershipModalProps) {
  const titleId = useId();
  const [acknowledged, setAcknowledged] = useState(false);
  const [typedConfirm, setTypedConfirm] = useState("");

  useEffect(() => {
    if (!open) {
      setAcknowledged(false);
      setTypedConfirm("");
    }
  }, [open]);

  if (!open || !target) return null;

  const expected = target.email ?? target.user_id;
  const canConfirm = acknowledged && typedConfirm.trim() === expected && !busy;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      data-testid="transfer-ownership-modal"
    >
      <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
        <h2 id={titleId} className="text-lg font-semibold text-slate-900">
          Transferir propriedade da organização
        </h2>

        <div className="mt-3 space-y-2 text-sm text-slate-700">
          <p>
            Você está prestes a transferir a propriedade para{" "}
            <strong className="font-semibold text-slate-900">{expected}</strong>.
          </p>
          <p className="rounded-md bg-amber-50 p-3 text-amber-900">
            Após a transferência, você se torna apenas membro e perde o
            acesso a configurações administrativas, billing e remoção
            de membros.
          </p>
        </div>

        <label className="mt-4 flex items-start gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={acknowledged}
            onChange={(e) => setAcknowledged(e.target.checked)}
            className="mt-0.5"
            data-testid="ack-checkbox"
          />
          <span>
            Eu entendo que esta ação é irreversível por mim mesmo — apenas
            o novo owner poderá me promover de volta.
          </span>
        </label>

        <label className="mt-3 block text-sm text-slate-700">
          <span className="mb-1 block">
            Para confirmar, digite{" "}
            <code className="rounded bg-slate-100 px-1 py-0.5 text-xs font-mono text-slate-900">
              {expected}
            </code>
            :
          </span>
          <input
            type="text"
            value={typedConfirm}
            onChange={(e) => setTypedConfirm(e.target.value)}
            disabled={!acknowledged}
            className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:bg-slate-50 disabled:opacity-50"
            data-testid="typed-confirm-input"
          />
        </label>

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            data-testid="cancel-transfer"
          >
            Cancelar
          </button>
          <button
            type="button"
            disabled={!canConfirm}
            onClick={() => target && onConfirm(target)}
            className="rounded-md bg-amber-600 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-700 focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:cursor-not-allowed disabled:opacity-50"
            data-testid="confirm-transfer"
          >
            {busy ? "Transferindo…" : "Transferir agora"}
          </button>
        </div>
      </div>
    </div>
  );
}
