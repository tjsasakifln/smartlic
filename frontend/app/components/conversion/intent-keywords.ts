/**
 * intent-keywords.ts — CONV-007-2
 *
 * Keyword mappings for IntentRouter intent detection.
 * Each cluster has 20+ keywords for robust detection.
 *
 * 4 clusters:
 * - comercial:   Vender / fornecer para o governo
 * - investigativa: Pesquisar mercado / concorrentes
 * - juridica:    Recursos / impugnacoes / aspectos legais
 * - subcontratacao: Terceirizacao / consorcios / subempreitada
 *
 * Fallback: cluster "geral" com oferta generica.
 */

export type IntentCluster = 'comercial' | 'investigativa' | 'juridica' | 'subcontratacao' | 'geral';

export type DetectionSource = 'search_term' | 'referrer' | 'fallback';

/**
 * 20+ keywords per cluster for search term intent detection.
 * Multi-word phrases are checked via String.includes().
 */
export const CLUSTER_KEYWORDS: Record<Exclude<IntentCluster, 'geral'>, string[]> = {
  comercial: [
    'vender',
    'venda',
    'fornecedor',
    'licitar',
    'proposta',
    'participar',
    'concorrência pública',
    'pregão',
    'tomar conta',
    'prospectar',
    'cotação',
    'preço',
    'margem',
    'faturamento',
    'licitante',
    'vencedor',
    'homologação',
    'adjudicação',
    'contrato público',
    'proposta comercial',
    'como vender',
    'quero vender',
  ],
  investigativa: [
    'pesquisar',
    'pesquisa',
    'analisar',
    'análise',
    'concorrente',
    'mercado',
    'relatório',
    'estudo',
    'benchmark',
    'comparar',
    'tendência',
    'histórico',
    'dados',
    'estatística',
    'mapeamento',
    'diagnóstico',
    'monitoramento',
    'indicador',
    'intelligence',
    'análise setorial',
    'estudo de mercado',
    'investigar',
  ],
  juridica: [
    'impugnação',
    'recurso',
    'jurídico',
    'advogado',
    'parecer',
    'contestar',
    'questionamento',
    'legal',
    'norma',
    'regulamento',
    'lei 14.133',
    'decreto',
    'portaria',
    'cláusula',
    'habilitação',
    'documentação',
    'recurso administrativo',
    'mandado de segurança',
    'ação judicial',
    'consultoria jurídica',
    'compliance',
    'conformidade legal',
    'edital jurídico',
  ],
  subcontratacao: [
    'subcontratar',
    'subcontratação',
    'terceirizar',
    'terceirização',
    'parceiro',
    'consórcio',
    'joint venture',
    'subempreitada',
    'subempreiteiro',
    'subfornecedor',
    'sublicitante',
    'fornecedor terceiro',
    'parceiro de negócio',
    'prestador de serviço',
    'sub-rogação',
    'cadeia de suprimentos',
    'supply chain',
    'subcontratado',
    'parceiro estratégico',
    'terceirizado',
    'subcontrato',
  ],
};

/**
 * Referrer hostname patterns for intent detection.
 *
 * Matching via hostnameIncludes() — checks the keyword appears as a
 * standalone segment (preceded/followed by dot or at start/end).
 * This prevents substring false-positives (e.g. "industria" not matching
 * "industrial") without using RegExp on URLs (CodeQL js/incomplete-url-regexp).
 */
export const REFERRER_PATTERNS: Record<Exclude<IntentCluster, 'geral'>, string[]> = {
  comercial: ['sebrae', 'abring', 'industria', 'comercio', 'associacao'],
  investigativa: ['gov.br', 'ibge', 'ipea', 'jornal', 'noticia'],
  juridica: ['jusbrasil', 'oab', 'trf', 'stj', 'tcu', 'conjur', 'migalhas'],
  subcontratacao: ['construcao', 'engenharia', 'fornecedore', 'b2b'],
};

/**
 * Human-readable labels for each intent cluster.
 */
export const CLUSTER_LABELS: Record<IntentCluster, string> = {
  comercial: 'Comercial',
  investigativa: 'Investigativa',
  juridica: 'Jurídica',
  subcontratacao: 'Subcontratação',
  geral: 'Geral',
};
