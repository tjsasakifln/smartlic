"use client";

/**
 * RBAC-ORG-001 — Role badge + role-control dropdown.
 *
 * Surfaces an organization member's role (owner | member | viewer) as
 * an accessible badge, plus an owner-only inline control to promote /
 * demote / remove the member. Conditional UI only shows actions the
 * current viewer is authorized to take.
 *
 * Used inside `app/organizations/[id]/members/page.tsx`.
 */

import { useState } from "react";

export type OrgRole = "owner" | "member" | "viewer";

export interface RoleControlsProps {
  /** The member being rendered (target of the actions). */
  member: {
    user_id: string;
    email?: string;
    role: OrgRole;
  };
  /** The current logged-in user's role on this org. */
  currentUserRole: OrgRole;
  /** The current logged-in user's id (used for self-leave detection). */
  currentUserId: string;
  /** True when an action is in flight (parent disables the row). */
  busy?: boolean;
  /** Owner-only callback: change `member.role` to `newRole`. */
  onRoleChange?: (member: RoleControlsProps["member"], newRole: OrgRole) => void;
  /** Remove the member entirely (owner removes anyone; member/viewer self-leave). */
  onRemove?: (member: RoleControlsProps["member"]) => void;
  /** Owner-only: open the 2-step transfer-ownership modal targeting this member. */
  onTransferOwnership?: (member: RoleControlsProps["member"]) => void;
}

const ROLE_LABEL: Record<OrgRole, string> = {
  owner: "Owner",
  member: "Membro",
  viewer: "Visualizador",
};

/** Tailwind styles per role badge, AA contrast verified. */
const ROLE_BADGE_CLASS: Record<OrgRole, string> = {
  owner:
    "bg-amber-100 text-amber-900 ring-1 ring-amber-200",
  member:
    "bg-blue-100 text-blue-900 ring-1 ring-blue-200",
  viewer:
    "bg-slate-100 text-slate-700 ring-1 ring-slate-200",
};

export function RoleBadge({ role }: { role: OrgRole }) {
  return (
    <span
      role="status"
      aria-label={`Papel: ${ROLE_LABEL[role]}`}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${ROLE_BADGE_CLASS[role]}`}
      data-testid={`role-badge-${role}`}
    >
      {ROLE_LABEL[role]}
    </span>
  );
}

export default function RoleControls({
  member,
  currentUserRole,
  currentUserId,
  busy = false,
  onRoleChange,
  onRemove,
  onTransferOwnership,
}: RoleControlsProps) {
  const isCurrentOwner = currentUserRole === "owner";
  const isSelf = currentUserId === member.user_id;
  const memberIsOwner = member.role === "owner";
  const [confirming, setConfirming] = useState(false);

  // ── Visibility rules (AC12) ────────────────────────────────────────────────
  // - Role-change dropdown: owner only, target ≠ themselves (cannot demote
  //   themselves directly — must use transfer-ownership flow).
  // - Remove button:
  //     * owner: any non-owner OR self
  //     * member/viewer: self only (leave)
  // - Transfer-ownership: owner only, target is non-owner accepted member.
  const canChangeRole = isCurrentOwner && !isSelf;
  const canRemove = isCurrentOwner || isSelf;
  const canTransferOwnership =
    isCurrentOwner && !isSelf && !memberIsOwner;

  return (
    <div
      className="flex flex-wrap items-center gap-2"
      data-testid="role-controls"
    >
      <RoleBadge role={member.role} />

      {canChangeRole && onRoleChange && (
        <label className="sr-only" htmlFor={`role-select-${member.user_id}`}>
          Alterar papel de {member.email ?? member.user_id}
        </label>
      )}
      {canChangeRole && onRoleChange && (
        <select
          id={`role-select-${member.user_id}`}
          value={member.role}
          disabled={busy}
          onChange={(e) =>
            onRoleChange(member, e.currentTarget.value as OrgRole)
          }
          className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-blue disabled:opacity-50"
          data-testid={`role-select-${member.user_id}`}
        >
          <option value="owner">Owner</option>
          <option value="member">Membro</option>
          <option value="viewer">Visualizador</option>
        </select>
      )}

      {canTransferOwnership && onTransferOwnership && (
        <button
          type="button"
          disabled={busy}
          onClick={() => onTransferOwnership(member)}
          className="rounded-md border border-amber-400 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-900 hover:bg-amber-100 focus:outline-none focus:ring-2 focus:ring-amber-500 disabled:opacity-50"
          data-testid={`transfer-ownership-${member.user_id}`}
        >
          Transferir propriedade
        </button>
      )}

      {canRemove && onRemove && (
        confirming ? (
          <span
            className="inline-flex items-center gap-1"
            role="group"
            aria-label="Confirmar remoção"
          >
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                setConfirming(false);
                onRemove(member);
              }}
              className="rounded-md bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
              data-testid={`confirm-remove-${member.user_id}`}
            >
              {isSelf ? "Sair" : "Remover"}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
            >
              Cancelar
            </button>
          </span>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => setConfirming(true)}
            className="rounded-md border border-red-300 bg-white px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 focus:outline-none focus:ring-2 focus:ring-red-500 disabled:opacity-50"
            data-testid={`remove-${member.user_id}`}
          >
            {isSelf ? "Sair da organização" : "Remover"}
          </button>
        )
      )}
    </div>
  );
}
