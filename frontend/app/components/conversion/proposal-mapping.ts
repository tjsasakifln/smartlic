/**
 * proposal-mapping.ts — Issue #1402 (CONV-010-1)
 *
 * Maps each entity type to headline template, insight field config, and CTA copy
 * for the Proposta Comercial block.
 *
 * 5 entity types: fornecedor, orgao, setor, municipio, contrato
 * (CNPJ pages use the same config as fornecedor)
 */

export type EntityType =
  | "fornecedor"
  | "orgao"
  | "setor"
  | "municipio"
  | "contrato";

/** Describes a single insight card rendered inside the proposal block */
export interface InsightConfig {
  id: string;
  icon: string;
  label: string;
  /**
   * Accessor path in entityData, e.g. "total_contratos" or "ufs_atuantes.length".
   * Supports simple dot notation for shallow nested objects.
   */
  accessor: string;
  format?: "number" | "currency" | "text";
  /** Fallback text when the value is null, undefined, or empty */
  fallback: string;
}

/** Complete proposal configuration for one entity type */
export interface ProposalConfig {
  /** Template string: {{name}} is replaced with entityName at render time */
  headline: string;
  /** Subtitle / value proposition */
  subtitle: string;
  /** 2-3 insight cards to display */
  insights: InsightConfig[];
  cta: {
    label: string;
    href: string;
    secondaryLabel?: string;
    secondaryHref?: string;
  };
}

const MAPPING: Record<EntityType, ProposalConfig> = {
  fornecedor: {
    headline: "Quer vencer mais licitações como {{name}}?",
    subtitle:
      "Análise concorrencial com precificação inteligente e alertas automáticos de novos editais.",
    insights: [
      {
        id: "contratos",
        icon: "📋",
        label: "Contratos",
        accessor: "total_contratos",
        format: "number",
        fallback: "Dados disponíveis",
      },
      {
        id: "valor-total",
        icon: "💰",
        label: "Valor Total",
        accessor: "valor_total",
        format: "currency",
        fallback: "Dados disponíveis",
      },
      {
        id: "ufs",
        icon: "📍",
        label: "Estados de Atuação",
        accessor: "ufs_atuantes.length",
        format: "number",
        fallback: "Dados disponíveis",
      },
    ],
    cta: { label: "Testar grátis", href: "/signup?ref=proposta-fornecedor" },
  },

  orgao: {
    headline: "Quer vender para {{name}}?",
    subtitle:
      "Editais abertos, contratos anteriores e contatos diretos do órgão público.",
    insights: [
      {
        id: "licitacoes",
        icon: "📊",
        label: "Licitações",
        accessor: "total_licitacoes",
        format: "number",
        fallback: "Dados disponíveis",
      },
      {
        id: "licitacoes-30d",
        icon: "🔥",
        label: "Últimos 30 dias",
        accessor: "licitacoes_30d",
        format: "number",
        fallback: "Dados disponíveis",
      },
      {
        id: "valor-medio",
        icon: "💰",
        label: "Ticket Médio",
        accessor: "valor_medio_estimado",
        format: "currency",
        fallback: "Dados disponíveis",
      },
    ],
    cta: { label: "Testar grátis", href: "/signup?ref=proposta-orgao" },
  },

  setor: {
    headline: "Atue em {{name}} com inteligência",
    subtitle:
      "Oportunidades mapeadas, concorrentes identificados e preços de referência do setor.",
    insights: [
      {
        id: "oportunidades",
        icon: "🎯",
        label: "Oportunidades",
        accessor: "total_oportunidades",
        format: "number",
        fallback: "Dados disponíveis",
      },
      {
        id: "concorrentes",
        icon: "🏢",
        label: "Concorrentes",
        accessor: "concorrentes_count",
        format: "number",
        fallback: "Dados disponíveis",
      },
      {
        id: "preco-medio",
        icon: "📈",
        label: "Preço Médio",
        accessor: "preco_medio",
        format: "currency",
        fallback: "Dados disponíveis",
      },
    ],
    cta: {
      label: "Testar grátis",
      href: "/signup?ref=proposta-setor",
    },
  },

  municipio: {
    headline: "Licitações em {{name}}",
    subtitle:
      "Editais locais, contratos da prefeitura e oportunidades na câmara municipal.",
    insights: [
      {
        id: "editais",
        icon: "📋",
        label: "Editais",
        accessor: "total_editais",
        format: "number",
        fallback: "Dados disponíveis",
      },
      {
        id: "orgaos",
        icon: "🏛️",
        label: "Órgãos",
        accessor: "orgaos_count",
        format: "number",
        fallback: "Dados disponíveis",
      },
      {
        id: "valor-total",
        icon: "💰",
        label: "Valor Total",
        accessor: "valor_total_estimado",
        format: "currency",
        fallback: "Dados disponíveis",
      },
    ],
    cta: {
      label: "Testar grátis",
      href: "/signup?ref=proposta-municipio",
    },
  },

  contrato: {
    headline: "Contratos como este merecem análise",
    subtitle:
      "Análise detalhada do contrato, identificação de renovações e concorrentes do mesmo segmento.",
    insights: [
      {
        id: "analise",
        icon: "🔍",
        label: "Valor do Contrato",
        accessor: "valor_contrato",
        format: "currency",
        fallback: "Dados disponíveis",
      },
      {
        id: "renovacoes",
        icon: "🔄",
        label: "Renovações",
        accessor: "renovacoes_count",
        format: "number",
        fallback: "Dados disponíveis",
      },
      {
        id: "concorrentes",
        icon: "🏢",
        label: "Concorrentes",
        accessor: "concorrentes_count",
        format: "number",
        fallback: "Dados disponíveis",
      },
    ],
    cta: {
      label: "Testar grátis",
      href: "/signup?ref=proposta-contrato",
    },
  },
};

/** Retrieve the proposal config for a given entity type */
export function getProposalConfig(pageType: EntityType): ProposalConfig {
  return MAPPING[pageType];
}

/**
 * Format a raw value for display in insight cards.
 * Handles null/undefined gracefully and formats numbers/currency in pt-BR locale.
 */
export function formatInsightValue(
  value: unknown,
  format?: "number" | "currency" | "text",
): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "Sim" : "Não";
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);

  switch (format) {
    case "number":
      return num.toLocaleString("pt-BR");
    case "currency":
      return num.toLocaleString("pt-BR", {
        style: "currency",
        currency: "BRL",
        maximumFractionDigits: 0,
      });
    default:
      return String(value);
  }
}
