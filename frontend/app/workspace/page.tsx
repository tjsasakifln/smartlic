"use client";

import { useEffect, useState } from "react";
import { useAuth } from "../components/AuthProvider";
import { WorkspaceShell } from "../../components/workspace/WorkspaceShell";
import { EditaisHojeWidget } from "../../components/workspace/EditaisHojeWidget";
import { PipelineRapidoWidget } from "../../components/workspace/PipelineRapidoWidget";
import { AlertasWidget } from "../../components/workspace/AlertasWidget";
import { AcoesRapidasWidget } from "../../components/workspace/AcoesRapidasWidget";
import { AuthLoadingScreen } from "../../components/AuthLoadingScreen";
import { ErrorStateWithRetry } from "../../components/ErrorStateWithRetry";

interface EditaisHojeItem {
  pncp_id?: string | null;
  orgao?: string | null;
  uf?: string | null;
  objeto?: string | null;
  valor_estimado?: number | null;
  data_publicacao?: string | null;
  data_encerramento?: string | null;
  link_pncp?: string | null;
  modalidade?: string | null;
  numero_compra?: string | null;
}

interface PipelineItem {
  id: string;
  stage: string;
  objeto?: string | null;
  orgao?: string | null;
  data_encerramento?: string | null;
  valor_estimado?: number | null;
  is_expired?: boolean;
}

interface WorkspaceResumo {
  editais_hoje_count: number;
  pipeline_count: number;
  pipeline_prazo_proximo: number;
  alerts_unread_count: number;
}

export default function WorkspacePage() {
  const { session, loading: authLoading } = useAuth();

  const [editais, setEditais] = useState<EditaisHojeItem[]>([]);
  const [editaisTotal, setEditaisTotal] = useState(0);
  const [editaisLoading, setEditaisLoading] = useState(true);

  const [pipelineItems, setPipelineItems] = useState<PipelineItem[]>([]);
  const [pipelineTotal, setPipelineTotal] = useState(0);
  const [pipelineLoading, setPipelineLoading] = useState(true);

  const [alertsUnread, setAlertsUnread] = useState(0);
  const [alertsLoading, setAlertsLoading] = useState(true);

  const [prazosProximos, setPrazosProximos] = useState(0);
  const [resumoLoading, setResumoLoading] = useState(true);

  const [error, setError] = useState<string | null>(null);

  const fetchWorkspaceData = async () => {
    setError(null);

    try {
      // Fetch editais do dia
      setEditaisLoading(true);
      const editaisRes = await fetch("/api/workspace/editais-hoje", {
        headers: { authorization: `Bearer ${session?.access_token}` },
      });
      if (editaisRes.ok) {
        const editaisData = await editaisRes.json();
        setEditais(editaisData.items ?? []);
        setEditaisTotal(editaisData.total ?? 0);
      }
    } catch (e) {
      console.error("Error fetching editais-hoje:", e);
    } finally {
      setEditaisLoading(false);
    }

    try {
      // Fetch pipeline items (top 5)
      setPipelineLoading(true);
      const pipelineRes = await fetch("/api/pipeline?_path=/pipeline&limit=5&offset=0", {
        headers: { authorization: `Bearer ${session?.access_token}` },
      });
      if (pipelineRes.ok) {
        const pipelineData = await pipelineRes.json();
        setPipelineItems(pipelineData.items ?? []);
        setPipelineTotal(pipelineData.total ?? 0);
      }
    } catch (e) {
      console.error("Error fetching pipeline:", e);
    } finally {
      setPipelineLoading(false);
    }

    try {
      // Fetch resumo (aggregated counts)
      setResumoLoading(true);
      const resumoRes = await fetch("/api/workspace/resumo", {
        headers: { authorization: `Bearer ${session?.access_token}` },
      });
      if (resumoRes.ok) {
        const resumo: WorkspaceResumo = await resumoRes.json();
        setAlertsUnread(resumo.alerts_unread_count ?? 0);
        setPrazosProximos(resumo.pipeline_prazo_proximo ?? 0);
      }
    } catch (e) {
      console.error("Error fetching workspace resumo:", e);
    } finally {
      setResumoLoading(false);
    }
  };

  useEffect(() => {
    if (session?.access_token) {
      fetchWorkspaceData();
    }
  }, [session?.access_token]);

  if (authLoading) {
    return <AuthLoadingScreen />;
  }

  if (!session) {
    return null; // Will redirect via NavigationShell auth guard
  }

  return (
    <WorkspaceShell>
      {error && (
        <div className="mb-6">
          <ErrorStateWithRetry
            message={error}
            onRetry={fetchWorkspaceData}
          />
        </div>
      )}

      {/* Summary cards row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <SummaryCard
          label="Editais Hoje"
          value={editaisTotal}
          loading={editaisLoading}
          color="text-blue-500"
        />
        <SummaryCard
          label="Pipeline"
          value={pipelineTotal}
          loading={pipelineLoading}
          color="text-amber-500"
        />
        <SummaryCard
          label="Prazos Proximos"
          value={prazosProximos}
          loading={resumoLoading}
          color="text-purple-500"
        />
        <SummaryCard
          label="Alertas"
          value={alertsUnread}
          loading={alertsLoading}
          color="text-red-500"
        />
      </div>

      {/* Widgets grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <EditaisHojeWidget
          items={editais}
          total={editaisTotal}
          loading={editaisLoading}
        />
        <PipelineRapidoWidget
          items={pipelineItems}
          total={pipelineTotal}
          loading={pipelineLoading}
        />
        <AlertasWidget
          unreadCount={alertsUnread}
          loading={alertsLoading}
        />
        <AcoesRapidasWidget />
      </div>
    </WorkspaceShell>
  );
}

function SummaryCard({
  label,
  value,
  loading,
  color,
}: {
  label: string;
  value: number;
  loading: boolean;
  color: string;
}) {
  return (
    <div className="bg-[var(--surface-0)] rounded-xl border border-[var(--border)] shadow-sm p-4">
      <p className="text-xs font-medium text-[var(--ink-muted)] uppercase tracking-wider">{label}</p>
      {loading ? (
        <div className="h-8 w-16 mt-1 bg-[var(--surface-1)] animate-pulse rounded" />
      ) : (
        <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      )}
    </div>
  );
}
