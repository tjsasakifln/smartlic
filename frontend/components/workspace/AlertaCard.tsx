"use client";

import { useState } from "react";
import {
  Bell,
  Clock,
  FileText,
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";

interface AlertaItem {
  id: string;
  tipo: string;
  titulo: string;
  descricao?: string;
  lido: boolean;
  created_at: string;
  metadata?: Record<string, unknown>;
}

interface AlertaCardProps {
  alerta: AlertaItem;
  onMarkRead?: (id: string) => void;
}

/** Map alert types to icons and colors. */
const TYPE_CONFIG: Record<
  string,
  { icon: React.ReactNode; color: string; bgColor: string }
> = {
  new_matching_edital: {
    icon: <Bell className="w-4 h-4" />,
    color: "text-blue-600 dark:text-blue-400",
    bgColor: "bg-blue-50 dark:bg-blue-900/20",
  },
  deadline_approaching: {
    icon: <Clock className="w-4 h-4" />,
    color: "text-amber-600 dark:text-amber-400",
    bgColor: "bg-amber-50 dark:bg-amber-900/20",
  },
  pregao_starting: {
    icon: <AlertTriangle className="w-4 h-4" />,
    color: "text-orange-600 dark:text-orange-400",
    bgColor: "bg-orange-50 dark:bg-orange-900/20",
  },
  result_published: {
    icon: <FileText className="w-4 h-4" />,
    color: "text-green-600 dark:text-green-400",
    bgColor: "bg-green-50 dark:bg-green-900/20",
  },
  contrato_firmado: {
    icon: <CheckCircle2 className="w-4 h-4" />,
    color: "text-emerald-600 dark:text-emerald-400",
    bgColor: "bg-emerald-50 dark:bg-emerald-900/20",
  },
};

const DEFAULT_CONFIG = {
  icon: <Bell className="w-4 h-4" />,
  color: "text-[var(--ink-secondary)]",
  bgColor: "bg-gray-50 dark:bg-gray-800",
};

/** Format ISO date to Brazilian locale string. */
function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Get a human-readable label for an alert type. */
function getTypeLabel(tipo: string): string {
  const labels: Record<string, string> = {
    new_matching_edital: "Novo Edital",
    deadline_approaching: "Prazo Pr&oacute;ximo",
    pregao_starting: "Preg&atilde;o Iniciando",
    result_published: "Resultado Publicado",
    contrato_firmado: "Contrato Firmado",
    documento_vencendo: "Documento Vencendo",
  };
  return labels[tipo] || tipo;
}

/**
 * AlertaCard — Displays a single alert with type-based styling,
 * mark-as-read action, and optional metadata extraction.
 */
export function AlertaCard({ alerta, onMarkRead }: AlertaCardProps) {
  const [isRead, setIsRead] = useState(alerta.lido);

  const cfg = TYPE_CONFIG[alerta.tipo] || DEFAULT_CONFIG;
  const editalId = alerta.metadata?.edital_id as string | undefined;

  const handleMarkRead = async () => {
    if (isRead) return;
    try {
      const res = await fetch(`/api/workspace/alertas/${alerta.id}/read`, {
        method: "PATCH",
      });
      if (res.ok) {
        setIsRead(true);
        onMarkRead?.(alerta.id);
      }
    } catch {
      // Silently fail — user can retry
    }
  };

  return (
    <div
      className={`
        relative flex gap-3 p-3 rounded-lg border transition-all
        ${isRead
          ? "border-[var(--border)] bg-[var(--surface-0)] opacity-75"
          : "border-[var(--brand-blue)]/20 bg-[var(--surface-1)] shadow-sm"
        }
      `}
    >
      {/* Unread indicator */}
      {!isRead && (
        <span className="absolute top-3 left-3 w-2 h-2 rounded-full bg-[var(--brand-blue)]" />
      )}

      {/* Type icon */}
      <div
        className={`
          flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center
          ${cfg.bgColor} ${cfg.color}
        `}
      >
        {cfg.icon}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-0.5">
          <span
            className={`text-[10px] font-semibold uppercase tracking-wider ${cfg.color}`}
          >
            {getTypeLabel(alerta.tipo)}
          </span>
          <span className="text-[10px] text-[var(--ink-faint)]">
            {formatDate(alerta.created_at)}
          </span>
        </div>

        <p className="text-sm font-medium text-[var(--ink)] leading-snug">
          {alerta.titulo}
        </p>

        {alerta.descricao && (
          <p className="text-xs text-[var(--ink-muted)] mt-1 line-clamp-2">
            {alerta.descricao}
          </p>
        )}

        {/* Actions */}
        <div className="flex items-center gap-3 mt-2">
          {!isRead && (
            <button
              onClick={handleMarkRead}
              className="text-[10px] font-medium text-[var(--brand-blue)] hover:text-[var(--brand-blue-dark)] transition-colors"
            >
              Marcar como lido
            </button>
          )}
          {editalId && (
            <a
              href={`https://pncp.gov.br/app/editais/${editalId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-[10px] text-[var(--ink-muted)] hover:text-[var(--ink)] transition-colors"
            >
              <ExternalLink className="w-3 h-3" />
              <span>Ver no PNCP</span>
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
