"use client";

import React, { useState } from "react";

export interface PredictiveAlert {
  id: string; sector_id: string; alert_type: AlertType;
  threshold_value: number; uf: string | null; enabled: boolean;
  last_triggered_at: string | null; created_at: string; updated_at: string;
}

export type AlertType = "volume_spike" | "new_opportunity" | "recurrence" | "deadline_approaching";

const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  volume_spike: "Pico de volume", new_opportunity: "Nova oportunidade",
  recurrence: "Recorrencia", deadline_approaching: "Prazo proximo",
};

const ALERT_TYPE_DESCS: Record<AlertType, string> = {
  volume_spike: "Disparado quando o volume de contratos previstos cresce >15% YoY",
  new_opportunity: "Notifica sobre qualquer nova oportunidade prevista para o setor",
  recurrence: "Ativado quando ha alta probabilidade de recorrencia (>50%)",
  deadline_approaching: "Alerta quando uma publicacao prevista esta a <2 meses",
};

const ALL_UFS = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"];

function formatCurrency(v: number): string {
  return new Intl.NumberFormat("pt-BR", {style:"currency",currency:"BRL",maximumFractionDigits:0}).format(v);
}
function formatDate(iso: string|null): string {
  return iso ? new Date(iso).toLocaleDateString("pt-BR") : "Nunca";
}

function AlertSkeleton() {
  return <div className="animate-pulse space-y-3" data-testid="alert-config-skeleton"><div className="h-8 bg-[var(--surface-1)] rounded-lg w-1/3"/><div className="h-20 bg-[var(--surface-1)] rounded-lg"/><div className="h-20 bg-[var(--surface-1)] rounded-lg"/></div>;
}

function AlertEmpty() {
  return <div className="flex flex-col items-center justify-center py-8 text-center" data-testid="alert-config-empty"><div className="w-10 h-10 rounded-full bg-[var(--surface-1)] flex items-center justify-center mb-2"><svg className="w-5 h-5 text-[var(--ink-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"/></svg></div><p className="text-[var(--ink-secondary)] font-medium">Nenhum alerta preditivo</p><p className="text-sm text-[var(--ink-muted)] mt-1">Crie alertas para ser notificado sobre oportunidades previstas</p></div>;
}

function AlertError({onRetry}:{onRetry:()=>void}) {
  return <div className="flex flex-col items-center justify-center py-8 text-center bg-[var(--surface-1)] rounded-xl" data-testid="alert-config-error"><div className="w-10 h-10 rounded-full bg-[var(--error-bg)] flex items-center justify-center mb-2"><svg className="w-5 h-5 text-[var(--error)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}><path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"/></svg></div><p className="text-[var(--error)] font-medium">Erro ao carregar alertas</p><button onClick={onRetry} className="mt-2 px-3 py-1.5 text-sm font-medium text-[var(--brand-blue)] hover:bg-[var(--surface-2)] rounded-lg transition-colors">Tentar novamente</button></div>;
}

export interface AlertConfigProps {
  alerts: PredictiveAlert[]; loading?: boolean; error?: string | null; onRetry?: () => void;
  availableSectors?: string[];
  onCreate?: (a:{sector_id:string;alert_type:AlertType;threshold_value:number;uf:string|null}) => void;
  onToggle?: (id:string,enabled:boolean) => void; onDelete?: (id:string) => void;
}

function CreateForm({sectors,onSubmit,onCancel}:{sectors:string[];onSubmit:(d:any)=>void;onCancel:()=>void}) {
  const [sid,setSid] = useState(sectors[0]||""); const [at,setAt] = useState<AlertType>("new_opportunity");
  const [tv,setTv] = useState(0); const [uf,setUf] = useState("");
  return <form onSubmit={e=>{e.preventDefault();if(sid)onSubmit({sector_id:sid,alert_type:at,threshold_value:tv,uf:uf||null});}} className="bg-[var(--surface-1)] rounded-xl p-4 space-y-3" data-testid="create-alert-form">
    <h4 className="text-sm font-semibold text-[var(--ink)]">Novo alerta preditivo</h4>
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div><label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">Setor</label>
        <select value={sid} onChange={e=>setSid(e.target.value)} required className="w-full px-2 py-1.5 text-sm bg-[var(--surface-0)] border border-[var(--border)] rounded-lg text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]" data-testid="create-alert-sector">
          <option value="">Selecione...</option>{sectors.map(s=><option key={s} value={s}>{s}</option>)}
        </select></div>
      <div><label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">Tipo</label>
        <select value={at} onChange={e=>setAt(e.target.value as AlertType)} required className="w-full px-2 py-1.5 text-sm bg-[var(--surface-0)] border border-[var(--border)] rounded-lg text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]" data-testid="create-alert-type">
          {Object.entries(ALERT_TYPE_LABELS).map(([v,l])=><option key={v} value={v}>{l}</option>)}
        </select></div>
      <div><label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">Valor minimo (R$)</label>
        <input type="number" min={0} step={1000} value={tv} onChange={e=>setTv(Number(e.target.value))} className="w-full px-2 py-1.5 text-sm bg-[var(--surface-0)] border border-[var(--border)] rounded-lg text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]" data-testid="create-alert-threshold"/></div>
      <div><label className="block text-xs font-medium text-[var(--ink-muted)] mb-1">UF (opcional)</label>
        <select value={uf} onChange={e=>setUf(e.target.value)} className="w-full px-2 py-1.5 text-sm bg-[var(--surface-0)] border border-[var(--border)] rounded-lg text-[var(--ink)] focus:outline-none focus:ring-2 focus:ring-[var(--brand-blue)]" data-testid="create-alert-uf">
          <option value="">Todas</option>{ALL_UFS.map(u=><option key={u} value={u}>{u}</option>)}
        </select></div>
    </div>
    <p className="text-xs text-[var(--ink-muted)]">{ALERT_TYPE_DESCS[at]}</p>
    <div className="flex gap-2 justify-end"><button type="button" onClick={onCancel} className="px-3 py-1.5 text-sm font-medium text-[var(--ink-secondary)] hover:bg-[var(--surface-2)] rounded-lg">Cancelar</button>
      <button type="submit" className="px-3 py-1.5 text-sm font-medium text-white bg-[var(--brand-blue)] hover:opacity-90 rounded-lg" data-testid="create-alert-submit">Criar alerta</button></div>
  </form>;
}

function AlertCard({alert,onToggle,onDelete}:{alert:PredictiveAlert;onToggle?:(id:string,e:boolean)=>void;onDelete?:(id:string)=>void}) {
  return <div className={`bg-[var(--surface-1)] rounded-xl p-4 transition-opacity ${alert.enabled?"":"opacity-60"}`} data-testid={`alert-card-${alert.id}`}>
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-[var(--ink)]">{ALERT_TYPE_LABELS[alert.alert_type]}</span>
          <span className="px-2 py-0.5 text-[10px] font-medium bg-[var(--surface-2)] text-[var(--ink-secondary)] rounded-full">{alert.sector_id}</span>
          {alert.uf && <span className="px-2 py-0.5 text-[10px] font-medium bg-[var(--surface-2)] text-[var(--ink-secondary)] rounded-full">{alert.uf}</span>}
        </div>
        <div className="mt-1.5 space-y-0.5">
          <p className="text-xs text-[var(--ink-muted)]">{ALERT_TYPE_DESCS[alert.alert_type]}</p>
          <p className="text-xs text-[var(--ink-muted)]">Valor minimo: {formatCurrency(alert.threshold_value)}{alert.threshold_value===0?" (sem limite)":""}</p>
          <p className="text-xs text-[var(--ink-muted)]">Ultima execucao: {formatDate(alert.last_triggered_at)}</p>
        </div>
      </div>
      <div className="flex items-center gap-2 flex-shrink-0">
        {onToggle && <button onClick={()=>onToggle(alert.id,!alert.enabled)} className={`relative w-10 h-5 rounded-full transition-colors ${alert.enabled?"bg-[var(--brand-blue)]":"bg-[var(--surface-2)]"}`} aria-label={alert.enabled?"Desativar alerta":"Ativar alerta"} data-testid={`alert-toggle-${alert.id}`}><span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${alert.enabled?"translate-x-5":"translate-x-0.5"}`}/></button>}
        {onDelete && <button onClick={()=>onDelete(alert.id)} className="p-1 rounded-md hover:bg-[var(--surface-2)] text-[var(--ink-muted)] hover:text-[var(--error)] transition-colors" aria-label="Remover alerta" data-testid={`alert-delete-${alert.id}`}><svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg></button>}
      </div>
    </div>
  </div>;
}

export function AlertConfig({alerts,loading=false,error=null,onRetry,availableSectors=[],onCreate,onToggle,onDelete}:AlertConfigProps) {
  const [showForm,setShowForm] = useState(false);
  if (loading) return <AlertSkeleton/>;
  if (error) return <AlertError onRetry={onRetry||(()=>{})}/>;
  return <div className="space-y-4" data-testid="alert-config">
    <div className="flex items-center justify-between">
      <div><h3 className="text-lg font-semibold text-[var(--ink)]">Alertas Preditivos</h3><p className="text-sm text-[var(--ink-muted)]">Receba notificacoes sobre oportunidades previstas</p></div>
      {onCreate && <button onClick={()=>setShowForm(!showForm)} className="px-3 py-1.5 text-sm font-medium text-white bg-[var(--brand-blue)] hover:opacity-90 rounded-lg" data-testid="alert-config-add-button">{showForm?"Cancelar":"+ Novo alerta"}</button>}
    </div>
    {showForm && onCreate && <CreateForm sectors={availableSectors} onSubmit={d=>{onCreate(d);setShowForm(false);}} onCancel={()=>setShowForm(false)}/>}
    {alerts.length===0 ? <AlertEmpty/> : <div className="space-y-2">{alerts.map(a=><AlertCard key={a.id} alert={a} onToggle={onToggle} onDelete={onDelete}/>)}</div>}
  </div>;
}
