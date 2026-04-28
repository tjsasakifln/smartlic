"use client";

/**
 * RBAC-ORG-001 — Organization members management page.
 *
 * Authoritative server-side enforcement is in `routes/organizations.py`
 * via `require_org_role(...)`. This page mirrors the same matrix in the
 * UI: actions the user is not authorized for are NOT rendered (FOUC
 * prevention via SSR-loaded role).
 *
 * AC10: role badges + dropdown promote/demote (visible only to owner)
 * AC11: 2-step transfer-ownership modal
 * AC12: hide controls user cannot use (no "Convidar" for viewer/member)
 */

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import RoleControls, { type OrgRole } from "@/components/organizations/RoleControls";
import TransferOwnershipModal from "@/components/organizations/TransferOwnershipModal";

interface Member {
  user_id: string;
  email?: string;
  role: OrgRole;
  invited_at?: string | null;
  accepted_at?: string | null;
}

interface OrgDetail {
  id: string;
  name: string;
  user_role: OrgRole;
  members: Member[];
}

export default function OrgMembersPage() {
  const params = useParams<{ id: string }>();
  const orgId = params?.id ?? "";

  const [org, setOrg] = useState<OrgDetail | null>(null);
  const [currentUserId, setCurrentUserId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyMemberId, setBusyMemberId] = useState<string | null>(null);

  // Invite form
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviting, setInviting] = useState(false);

  // Transfer-ownership modal
  const [transferTarget, setTransferTarget] = useState<Member | null>(null);
  const [transferring, setTransferring] = useState(false);

  const refresh = useCallback(async () => {
    if (!orgId) return;
    setLoading(true);
    try {
      const [orgResp, userResp] = await Promise.all([
        fetch(`/api/organizations/${orgId}`),
        fetch("/api/me"),
      ]);
      if (!orgResp.ok) {
        if (orgResp.status === 403)
          throw new Error("Você não tem permissão para ver esta organização.");
        if (orgResp.status === 404)
          throw new Error("Organização não encontrada.");
        throw new Error("Falha ao carregar organização.");
      }
      const orgData = await orgResp.json();
      setOrg(orgData);
      if (userResp.ok) {
        const me = await userResp.json();
        setCurrentUserId(me?.id ?? "");
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro inesperado.");
    } finally {
      setLoading(false);
    }
  }, [orgId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const isOwner = org?.user_role === "owner";

  // ── Action handlers ─────────────────────────────────────────────────────────

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    setInviting(true);
    try {
      const resp = await fetch(`/api/organizations/${orgId}/invite`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: inviteEmail.trim() }),
      });
      if (!resp.ok) {
        const detail = (await resp.json().catch(() => ({}))).detail;
        throw new Error(detail || `Falha ao convidar (${resp.status})`);
      }
      setInviteEmail("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao convidar.");
    } finally {
      setInviting(false);
    }
  }

  async function handleRoleChange(member: Member, newRole: OrgRole) {
    setBusyMemberId(member.user_id);
    try {
      const resp = await fetch(
        `/api/organizations/${orgId}/members/${member.user_id}/role`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ role: newRole }),
        }
      );
      if (!resp.ok) {
        const detail = (await resp.json().catch(() => ({}))).detail;
        throw new Error(detail || `Falha ao alterar papel (${resp.status})`);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao alterar papel.");
    } finally {
      setBusyMemberId(null);
    }
  }

  async function handleRemove(member: Member) {
    setBusyMemberId(member.user_id);
    try {
      const resp = await fetch(
        `/api/organizations/${orgId}/members/${member.user_id}`,
        { method: "DELETE" }
      );
      if (!resp.ok) {
        const detail = (await resp.json().catch(() => ({}))).detail;
        throw new Error(detail || `Falha ao remover (${resp.status})`);
      }
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao remover.");
    } finally {
      setBusyMemberId(null);
    }
  }

  async function handleTransferConfirm(target: Member) {
    setTransferring(true);
    try {
      const resp = await fetch(
        `/api/organizations/${orgId}/transfer-ownership`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            target_user_id: target.user_id,
            confirm: true,
          }),
        }
      );
      if (!resp.ok) {
        const detail = (await resp.json().catch(() => ({}))).detail;
        throw new Error(detail || `Falha ao transferir (${resp.status})`);
      }
      setTransferTarget(null);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao transferir.");
    } finally {
      setTransferring(false);
    }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <main className="mx-auto max-w-4xl p-6">
        <p className="text-slate-600">Carregando…</p>
      </main>
    );
  }
  if (error && !org) {
    return (
      <main className="mx-auto max-w-4xl p-6">
        <div
          role="alert"
          className="rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-800"
        >
          {error}
        </div>
      </main>
    );
  }
  if (!org) return null;

  return (
    <main className="mx-auto max-w-4xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-900">
          Membros — {org.name}
        </h1>
        <p className="mt-1 text-sm text-slate-600">
          {org.members.length} membro{org.members.length === 1 ? "" : "s"}
        </p>
      </header>

      {error && (
        <div
          role="alert"
          className="mb-4 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-800"
          data-testid="error-banner"
        >
          {error}
        </div>
      )}

      {/* AC12: Convite só visível para owner */}
      {isOwner && (
        <form
          onSubmit={handleInvite}
          className="mb-6 flex gap-2"
          data-testid="invite-form"
        >
          <input
            type="email"
            value={inviteEmail}
            onChange={(e) => setInviteEmail(e.target.value)}
            placeholder="email@empresa.com"
            required
            className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-blue"
          />
          <button
            type="submit"
            disabled={inviting}
            className="rounded-md bg-brand-navy px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue-hover disabled:opacity-50"
          >
            {inviting ? "Convidando…" : "Convidar"}
          </button>
        </form>
      )}

      <ul
        className="divide-y divide-slate-200 rounded-md border border-slate-200 bg-white"
        data-testid="members-list"
      >
        {org.members.map((m) => (
          <li
            key={m.user_id}
            className="flex flex-wrap items-center justify-between gap-4 p-4"
            data-testid={`member-row-${m.user_id}`}
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-900">
                {m.email ?? m.user_id}
              </p>
              {!m.accepted_at && (
                <p className="text-xs text-amber-700">Convite pendente</p>
              )}
            </div>
            <RoleControls
              member={m}
              currentUserRole={org.user_role}
              currentUserId={currentUserId}
              busy={busyMemberId === m.user_id}
              onRoleChange={isOwner ? handleRoleChange : undefined}
              onRemove={handleRemove}
              onTransferOwnership={
                isOwner ? (target) => setTransferTarget(target) : undefined
              }
            />
          </li>
        ))}
      </ul>

      <TransferOwnershipModal
        open={transferTarget !== null}
        target={transferTarget}
        busy={transferring}
        onConfirm={handleTransferConfirm}
        onCancel={() => setTransferTarget(null)}
      />
    </main>
  );
}
