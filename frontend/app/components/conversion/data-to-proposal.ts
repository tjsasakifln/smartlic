/**
 * data-to-proposal.ts — CONV-010-2 (#1509)
 *
 * Maps entity data to proposal content based on entityType.
 * Provides value proposition text, supporting details, and insight cards
 * derived from the raw entity data object.
 */

import type { InsightIcon } from './AhaMomentPanel';

export interface ProposalContent {
  valueProp: string;
  supportingDetail?: string;
  insights: Array<{
    label: string;
    value: string;
    subtext?: string;
    icon?: InsightIcon;
  }>;
}

/**
 * Extract a string value from a nested object using an accessor path.
 * Falls back to a default value if the path is not found.
 */
function extractValue(
  data: Record<string, unknown>,
  path: string,
  defaultValue: string,
): string {
  const parts = path.split('.');
  let current: unknown = data;
  for (const part of parts) {
    if (current === null || current === undefined) return defaultValue;
    if (typeof current !== 'object') return defaultValue;
    current = (current as Record<string, unknown>)[part];
  }
  if (current === null || current === undefined) return defaultValue;
  return String(current);
}

/**
 * Format a number to Brazilian locale.
 */
function formatNumber(value: unknown): string {
  if (value === null || value === undefined) return '';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString('pt-BR');
}

/**
 * Format a number as BRL currency.
 */
function formatCurrency(value: unknown): string {
  if (value === null || value === undefined) return '';
  const num = Number(value);
  if (Number.isNaN(num)) return String(value);
  return num.toLocaleString('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  });
}

// ---------------------------------------------------------------------------
// Mapping functions per entity type
// ---------------------------------------------------------------------------

function mapFornecedor(
  entityName: string,
  data: Record<string, unknown>,
): ProposalContent {
  const contratos = extractValue(data, 'total_contratos', '—');
  const valorTotal = extractValue(data, 'valor_total', '—');
  const ufs = extractValue(data, 'ufs_atuantes', '—');

  return {
    valueProp: `Quer vencer mais licitações como ${entityName}?`,
    supportingDetail: `Análise concorrencial com precificação inteligente e alertas de novos editais no seu setor.`,
    insights: [
      {
        label: 'Contratos Ganhos',
        value: contratos,
        icon: 'chart',
        subtext: 'Total de contratos registrados',
      },
      {
        label: 'Ticket Médio',
        value: valorTotal,
        icon: 'money',
        subtext: 'Valor total contratado',
      },
      {
        label: 'Atuação',
        value: ufs,
        icon: 'building',
        subtext: 'Estados onde atua',
      },
    ],
  };
}

function mapOrgao(
  entityName: string,
  data: Record<string, unknown>,
): ProposalContent {
  const editais = extractValue(data, 'total_licitacoes', '—');
  const contratosAtivos = extractValue(data, 'contratos_ativos', '—');
  const valorTotal = extractValue(data, 'valor_total_estimado', '—');

  return {
    valueProp: `Quer vender para ${entityName}?`,
    supportingDetail: `Editais abertos, contratos anteriores e contatos diretos do órgão público.`,
    insights: [
      {
        label: 'Editais Abertos',
        value: editais,
        icon: 'target',
        subtext: 'Oportunidades em aberto',
      },
      {
        label: 'Contratos Ativos',
        value: contratosAtivos,
        icon: 'chart',
        subtext: 'Contratos vigentes',
      },
      {
        label: 'Valor Total',
        value: valorTotal,
        icon: 'money',
        subtext: 'Total contratado pelo órgão',
      },
    ],
  };
}

function mapCnpj(
  entityName: string,
  data: Record<string, unknown>,
): ProposalContent {
  const participacoes = extractValue(data, 'participacoes', '—');
  const contratos = extractValue(data, 'contratos_obtidos', '—');
  const geografia = extractValue(data, 'presenca_geografica', '—');

  return {
    valueProp: `Dados completos do CNPJ ${entityName}`,
    supportingDetail: `Histórico completo de participações em licitações e contratos obtidos.`,
    insights: [
      {
        label: 'Participações',
        value: participacoes,
        icon: 'chart',
        subtext: 'Em licitações públicas',
      },
      {
        label: 'Contratos',
        value: contratos,
        icon: 'money',
        subtext: 'Contratos obtidos',
      },
      {
        label: 'Presença',
        value: geografia,
        icon: 'building',
        subtext: 'Presença geográfica',
      },
    ],
  };
}

function mapSetor(
  entityName: string,
  data: Record<string, unknown>,
): ProposalContent {
  const editais = extractValue(data, 'total_oportunidades', '—');
  const orgaos = extractValue(data, 'principais_orgaos', '—');
  const valorMedio = extractValue(data, 'valor_medio', '—');

  return {
    valueProp: `Atue em ${entityName} com inteligência`,
    supportingDetail: `Oportunidades mapeadas, concorrentes identificados e preços de referência do setor.`,
    insights: [
      {
        label: 'Editais no Setor',
        value: editais,
        icon: 'target',
        subtext: 'Oportunidades disponíveis',
      },
      {
        label: 'Principais Órgãos',
        value: orgaos,
        icon: 'building',
        subtext: 'Compradores do setor',
      },
      {
        label: 'Valor Médio',
        value: valorMedio,
        icon: 'money',
        subtext: 'Ticket médio por edital',
      },
    ],
  };
}

function mapMunicipio(
  entityName: string,
  data: Record<string, unknown>,
): ProposalContent {
  const editais = extractValue(data, 'total_editais', '—');
  const setores = extractValue(data, 'setores_principais', '—');
  const volume = extractValue(data, 'volume_contratacoes', '—');

  return {
    valueProp: `Licitações em ${entityName}`,
    supportingDetail: `Editais municipais, principais setores e volume de contratações da prefeitura.`,
    insights: [
      {
        label: 'Editais Municipais',
        value: editais,
        icon: 'target',
        subtext: 'Oportunidades no município',
      },
      {
        label: 'Setores',
        value: setores,
        icon: 'chart',
        subtext: 'Principais setores',
      },
      {
        label: 'Volume',
        value: volume,
        icon: 'money',
        subtext: 'Volume de contratações',
      },
    ],
  };
}

function mapContrato(
  entityName: string,
  data: Record<string, unknown>,
): ProposalContent {
  const renovacoes = extractValue(data, 'renovacoes_previstas', '—');
  const concorrentes = extractValue(data, 'concorrentes_ativos', '—');
  const valorSimilar = extractValue(data, 'valor_similar', '—');

  return {
    valueProp: `Contratos como este em ${entityName}`,
    supportingDetail: `Renovações previstas, concorrentes ativos e contratos de valor similar.`,
    insights: [
      {
        label: 'Renovações',
        value: renovacoes,
        icon: 'target',
        subtext: 'Renovações previstas',
      },
      {
        label: 'Concorrentes',
        value: concorrentes,
        icon: 'building',
        subtext: 'Concorrentes ativos',
      },
      {
        label: 'Valor Similar',
        value: valorSimilar,
        icon: 'money',
        subtext: 'Contratos de valor similar',
      },
    ],
  };
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

/**
 * Map entity data to proposal content based on entityType.
 *
 * @param entityType - The type of entity page
 * @param entityName - Display name of the entity
 * @param entityData - Raw entity data object
 * @returns ProposalContent with valueProp, supportingDetail, and insights
 *
 * @example
 * const proposal = mapEntityToProposal('fornecedor', 'Empresa ABC', { total_contratos: 42 });
 * // => { valueProp: 'Quer vencer mais licitações como Empresa ABC?', ... }
 */
export function mapEntityToProposal(
  entityType: string,
  entityName: string,
  entityData: Record<string, unknown>,
): ProposalContent {
  switch (entityType) {
    case 'fornecedor':
      return mapFornecedor(entityName, entityData);
    case 'orgao':
      return mapOrgao(entityName, entityData);
    case 'cnpj':
      return mapCnpj(entityName, entityData);
    case 'setor':
      return mapSetor(entityName, entityData);
    case 'municipio':
      return mapMunicipio(entityName, entityData);
    case 'contrato':
      return mapContrato(entityName, entityData);
    default:
      // Fallback for unknown entity types
      return {
        valueProp: `Análise inteligente para ${entityName}`,
        supportingDetail: 'Dados e insights para licitações públicas.',
        insights: [
          {
            label: 'Oportunidades',
            value: 'Consulte',
            icon: 'target',
          },
        ],
      };
  }
}
