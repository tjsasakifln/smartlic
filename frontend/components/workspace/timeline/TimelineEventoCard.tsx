"use client";

import {
  FileText,
  Pencil,
  AlertTriangle,
  MessageCircle,
  Trophy,
  CheckCircle,
  FileEdit,
  Bell,
} from "lucide-react";

export interface TimelineEvento {
  id: string;
  edital_id: string;
  tipo: string;
  titulo: string;
  descricao: string | null;
  critico: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
}

interface TimelineEventoCardProps {
  evento: TimelineEvento;
}

const TIPO_CONFIG: Record<
  string,
  { icon: React.ReactNode; label: string; color: string; bgColor: string }
> = {
  publicacao: {
    icon: <FileText size={16} />,
    label: "Publicacao",
    color: "text-blue-600",
    bgColor: "bg-blue-100",
  },
  alteracao: {
    icon: <Pencil size={16} />,
    label: "Alteracao",
    color: "text-yellow-600",
    bgColor: "bg-yellow-100",
  },
  impugnacao: {
    icon: <AlertTriangle size={16} />,
    label: "Impugnacao",
    color: "text-red-600",
    bgColor: "bg-red-100",
  },
  esclarecimento: {
    icon: <MessageCircle size={16} />,
    label: "Esclarecimento",
    color: "text-purple-600",
    bgColor: "bg-purple-100",
  },
  resultado: {
    icon: <Trophy size={16} />,
    label: "Resultado",
    color: "text-emerald-600",
    bgColor: "bg-emerald-100",
  },
  homologacao: {
    icon: <CheckCircle size={16} />,
    label: "Homologacao",
    color: "text-green-600",
    bgColor: "bg-green-100",
  },
  nota_manual: {
    icon: <FileEdit size={16} />,
    label: "Nota",
    color: "text-gray-600",
    bgColor: "bg-gray-100",
  },
  lembrete: {
    icon: <Bell size={16} />,
    label: "Lembrete",
    color: "text-orange-600",
    bgColor: "bg-orange-100",
  },
};

function formatDate(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export function TimelineEventoCard({ evento }: TimelineEventoCardProps) {
  const config = TIPO_CONFIG[evento.tipo] ?? {
    icon: <FileText size={16} />,
    label: evento.tipo,
    color: "text-gray-600",
    bgColor: "bg-gray-100",
  };

  return (
    <div
      className={`relative flex gap-4 p-4 rounded-xl border transition-colors ${
        evento.critico
          ? "border-red-200 bg-red-50/50"
          : "border-[var(--border)] bg-white"
      }`}
      data-testid={`timeline-event-${evento.id}`}
    >
      {/* Indicador critico */}
      {evento.critico && (
        <div className="absolute -top-2 -right-2">
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
            <AlertTriangle size={12} />
            Critico
          </span>
        </div>
      )}

      {/* Icone por tipo */}
      <div
        className={`flex-shrink-0 w-10 h-10 rounded-full ${config.bgColor} ${config.color} flex items-center justify-center`}
      >
        {config.icon}
      </div>

      {/* Conteudo */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded-full ${config.bgColor} ${config.color}`}
          >
            {config.label}
          </span>
          <span className="text-xs text-[var(--ink-tertiary)]">
            {formatDate(evento.created_at)}
          </span>
        </div>

        <h4 className="text-sm font-semibold text-[var(--ink)]">
          {evento.titulo}
        </h4>

        {evento.descricao && (
          <p className="mt-1 text-sm text-[var(--ink-secondary)] whitespace-pre-wrap">
            {evento.descricao}
          </p>
        )}
      </div>
    </div>
  );
}
