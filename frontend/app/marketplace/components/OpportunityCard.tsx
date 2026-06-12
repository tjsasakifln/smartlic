"use client";

import { Button } from "@/components/ui/button";

// --- Types (matching backend schema) ---

interface SubcontractOpportunity {
  id: string;
  contract_id: string | null;
  winner_cnpj: string;
  winner_name: string | null;
  sector: string | null;
  value: number | null;
  services_needed: string[];
  status: string;
  uf: string | null;
  municipio: string | null;
  orgao_nome: string | null;
  objeto: string | null;
  discovery_reason: string | null;
  created_at: string;
  interest_count: number;
}

// --- Helpers ---

function formatCurrency(value: number | null): string {
  if (value === null || value === undefined) return "Valor não informado";
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(date);
  } catch {
    return dateStr;
  }
}

function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen) + "...";
}

const SECTOR_LABELS: Record<string, string> = {
  construcao_civil: "Construção Civil",
  engenharia: "Engenharia",
  engenharia_rodoviaria: "Engenharia Rodoviária",
  informatica: "Informática / TI",
  software_desenvolvimento: "Desenvolvimento de Software",
  manutencao_predial: "Manutenção Predial",
  servicos_prediais: "Serviços Prediais",
};

function getSectorLabel(sector: string | null): string {
  if (!sector) return "Geral";
  return SECTOR_LABELS[sector] || sector;
}

// --- Component ---

interface OpportunityCardProps {
  opportunity: SubcontractOpportunity;
  hasInterest: boolean;
  onInterest: () => void;
}

export function OpportunityCard({
  opportunity,
  hasInterest,
  onInterest,
}: OpportunityCardProps) {
  return (
    <div
      className="rounded-xl border border-[var(--border-primary)] bg-[var(--surface-1)] p-5 hover:shadow-md transition-shadow"
      data-testid={`opportunity-card-${opportunity.id}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-[var(--text-primary)] truncate">
            {opportunity.winner_name || "Empresa não identificada"}
          </h3>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5">
            CNPJ: {opportunity.winner_cnpj}
          </p>
        </div>
        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-[var(--accent-soft)] text-[var(--accent-strong)]">
          {getSectorLabel(opportunity.sector)}
        </span>
      </div>

      {/* Value */}
      <div className="mb-3">
        <span className="text-lg font-bold text-[var(--accent-strong)]">
          {formatCurrency(opportunity.value)}
        </span>
      </div>

      {/* Details */}
      <div className="space-y-1.5 text-sm text-[var(--text-secondary)] mb-3">
        {opportunity.orgao_nome && (
          <p className="truncate" title={opportunity.orgao_nome}>
            <span className="font-medium text-[var(--text-primary)]">Órgão:</span>{" "}
            {opportunity.orgao_nome}
          </p>
        )}
        {opportunity.uf && (
          <p>
            <span className="font-medium text-[var(--text-primary)]">UF:</span>{" "}
            {opportunity.uf}
            {opportunity.municipio ? ` - ${opportunity.municipio}` : ""}
          </p>
        )}
        <p>
          <span className="font-medium text-[var(--text-primary)]">
            Interessados:
          </span>{" "}
          {opportunity.interest_count}
        </p>
        <p>
          <span className="font-medium text-[var(--text-primary)]">
            Publicado:
          </span>{" "}
          {formatDate(opportunity.created_at)}
        </p>
      </div>

      {/* Services needed */}
      {opportunity.services_needed.length > 0 && (
        <div className="mb-3">
          <p className="text-xs font-medium text-[var(--text-primary)] mb-1">
            Serviços necessários:
          </p>
          <div className="flex flex-wrap gap-1">
            {opportunity.services_needed.slice(0, 4).map((service, i) => (
              <span
                key={i}
                className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-[var(--surface-2)] text-[var(--text-secondary)]"
              >
                {truncate(service, 25)}
              </span>
            ))}
            {opportunity.services_needed.length > 4 && (
              <span className="text-xs text-[var(--text-secondary)]">
                +{opportunity.services_needed.length - 4}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Discovery reason */}
      {opportunity.discovery_reason && (
        <p className="text-xs text-[var(--text-tertiary)] mb-4 italic">
          {truncate(opportunity.discovery_reason, 120)}
        </p>
      )}

      {/* CTA */}
      <div className="flex gap-2">
        <Button
          variant="primary"
          size="sm"
          className="flex-1"
          onClick={onInterest}
          disabled={hasInterest}
          data-testid={`interest-btn-${opportunity.id}`}
        >
          {hasInterest ? "Interesse Registrado" : "Tenho Interesse"}
        </Button>
        <LinkButton opportunityId={opportunity.id} />
      </div>
    </div>
  );
}

function LinkButton({ opportunityId }: { opportunityId: string }) {
  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={() => {
        fetch(`/v1/marketplace/contact/${opportunityId}`, {
          method: "POST",
          credentials: "include",
        })
          .then(async (res) => {
            if (res.status === 402) {
              window.location.href = "/planos";
              return;
            }
            if (!res.ok) throw new Error("Erro ao carregar contato");
            const data = await res.json();
            // Build contact message
            const parts = [
              `Vencedor: ${data.winner_name || data.winner_cnpj}`,
              data.winner_email ? `Email: ${data.winner_email}` : null,
              data.winner_phone ? `Tel: ${data.winner_phone}` : null,
              data.orgao_nome ? `Órgão: ${data.orgao_nome}` : null,
              data.contract_value
                ? `Valor: ${new Intl.NumberFormat("pt-BR", {
                    style: "currency",
                    currency: "BRL",
                    maximumFractionDigits: 0,
                  }).format(data.contract_value)}`
                : null,
            ].filter(Boolean);
            alert(parts.join("\n"));
          })
          .catch(() => {
            window.location.href = "/planos";
          });
      }}
    >
      Ver Contato
    </Button>
  );
}
