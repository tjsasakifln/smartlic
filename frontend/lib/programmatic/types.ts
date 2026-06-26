/**
 * PSEO-002: Tipos, constantes, utilitarios e fetchers extraidos de lib/programmatic.ts.
 *
 * Fornece definicoes de tipo, mapeamentos setor<->slug, constantes de UF,
 * funcoes de formatacao, geracao de static params e data fetching.
 *
 * PSEO-P1-2048: Todos os fetch wrappers migrados para fetchWithBudget com
 * throwOn5xx: true. IS_BUILD_PHASE movido para lib/safe-fetch.ts.
 *
 * Estrategias B (IS_BUILD_PHASE inline) e C (ssgLimitedFetch + manual 5xx)
 * eliminadas em favor de fetchWithBudget unificado.
 */
import * as Sentry from '@sentry/nextjs';
import { fetchWithBudget } from '@/lib/safe-fetch';
import { SECTORS, type SectorMeta } from '@/lib/sectors';

// ---------------------------------------------------------------------------
// Sector slug <-> backend ID mappings
// ---------------------------------------------------------------------------

/** Slugs cujo ID no backend difere do padrao slug.replace(/-/g, '_'). */
export const SECTOR_SLUG_TO_BACKEND_ID: Record<string, string> = {
  software: 'software_desenvolvimento',
  facilities: 'servicos_prediais',
  saude: 'medicamentos',
  transporte: 'transporte_servicos',
};

/** Reverse mapping — backend sector ID -> frontend slug. */
export const BACKEND_ID_TO_FRONTEND_SLUG: Record<string, string> = {
  software_desenvolvimento: 'software',
  software_licencas: 'software',
  servicos_prediais: 'facilities',
  produtos_limpeza: 'facilities',
  medicamentos: 'saude',
  equipamentos_medicos: 'saude',
  insumos_hospitalares: 'saude',
  transporte_servicos: 'transporte',
  frota_veicular: 'transporte',
};

/** Converte backend sector ID para frontend URL slug. */
export function backendIdToFrontendSlug(backendId: string): string {
  return BACKEND_ID_TO_FRONTEND_SLUG[backendId] ?? backendId.replace(/_/g, '-');
}

// ---------------------------------------------------------------------------
// UF constants
// ---------------------------------------------------------------------------

export const ALL_UFS = [
  'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA',
  'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR', 'RJ', 'RN',
  'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
];

export const UF_NAMES: Record<string, string> = {
  AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapa',
  BA: 'Bahia', CE: 'Ceara', DF: 'Distrito Federal', ES: 'Espirito Santo',
  GO: 'Goias', MA: 'Maranhao', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul',
  MT: 'Mato Grosso', PA: 'Para', PB: 'Paraiba', PE: 'Pernambuco',
  PI: 'Piaui', PR: 'Parana', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte',
  RO: 'Rondonia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina',
  SE: 'Sergipe', SP: 'Sao Paulo', TO: 'Tocantins',
};

export const UF_PREPOSITIONS: Record<string, string> = {
  AC: 'no', AL: 'em', AM: 'no', AP: 'no', BA: 'na', CE: 'no',
  DF: 'no', ES: 'no', GO: 'em', MA: 'no', MG: 'em', MS: 'no',
  MT: 'no', PA: 'no', PB: 'na', PE: 'em', PI: 'no', PR: 'no',
  RJ: 'no', RN: 'no', RO: 'em', RR: 'em', RS: 'no', SC: 'em',
  SE: 'em', SP: 'em', TO: 'no',
};

/** Retorna a preposicao portuguesa correta para um estado brasileiro. */
export function getUfPrep(uf: string | undefined): string {
  if (!uf) return 'em';
  return UF_PREPOSITIONS[uf.toUpperCase()] ?? 'em';
}

// ---------------------------------------------------------------------------
// Region mappings (shared by editorial)
// ---------------------------------------------------------------------------

export type Region = 'sudeste' | 'sul' | 'nordeste' | 'norte' | 'centro_oeste';

export const UF_REGION: Record<string, Region> = {
  SP: 'sudeste', RJ: 'sudeste', MG: 'sudeste', ES: 'sudeste',
  PR: 'sul', SC: 'sul', RS: 'sul',
  BA: 'nordeste', PE: 'nordeste', CE: 'nordeste', MA: 'nordeste',
  PI: 'nordeste', RN: 'nordeste', PB: 'nordeste', AL: 'nordeste', SE: 'nordeste',
  AM: 'norte', PA: 'norte', AC: 'norte', RO: 'norte', RR: 'norte', AP: 'norte', TO: 'norte',
  GO: 'centro_oeste', MT: 'centro_oeste', MS: 'centro_oeste', DF: 'centro_oeste',
};

export const REGION_NAMES: Record<Region, string> = {
  sudeste: 'Sudeste',
  sul: 'Sul',
  nordeste: 'Nordeste',
  norte: 'Norte',
  centro_oeste: 'Centro-Oeste',
};

// ---------------------------------------------------------------------------
// Phased launch config
// ---------------------------------------------------------------------------

/** Phase 1 sectors — 5 largest by procurement volume */
export const PHASE1_SECTORS = ['informatica', 'saude', 'engenharia', 'facilities', 'software'];

/** Phase 1 UFs — 5 largest by procurement volume */
export const PHASE1_UFS = ['SP', 'RJ', 'MG', 'PR', 'RS'];

// ---------------------------------------------------------------------------
// Interfaces / Types
// ---------------------------------------------------------------------------

export interface SectorBlogStats {
  sector_id: string;
  sector_name: string;
  total_editais: number;
  value_range_min: number;
  value_range_max: number;
  avg_value: number;
  top_modalidades: { name: string; count: number }[];
  top_ufs: { name: string; count: number }[];
  trend_90d: { period: string; count: number; avg_value: number }[];
  last_updated: string;
}

export interface SectorUfStats {
  sector_id: string;
  sector_name: string;
  uf: string;
  total_editais: number;
  avg_value: number;
  value_range_min: number;
  value_range_max: number;
  top_modalidades: { name: string; count: number }[];
  trend_90d: { period: string; count: number; avg_value: number }[];
  top_oportunidades: {
    titulo: string;
    orgao: string;
    orgao_cnpj?: string | null;
    valor: number | null;
    uf: string;
    data: string;
  }[];
  last_updated: string;
  most_recent_bid_date?: string;
  municipios_ativos?: number;
  vs_media_nacional_pct?: number | null;
  top_compradores?: {
    nome: string;
    cnpj: string;
    total_contratos: number;
    valor_total: number;
  }[];
}

export interface PanoramaStats {
  sector_id: string;
  sector_name: string;
  total_nacional: number;
  total_value: number;
  avg_value: number;
  top_ufs: { name: string; count: number }[];
  top_modalidades: { name: string; count: number }[];
  sazonalidade: { period: string; count: number; avg_value: number }[];
  crescimento_estimado_pct: number;
  last_updated: string;
}

export interface AlertaBid {
  titulo: string;
  orgao: string;
  valor: number | null;
  uf: string;
  municipio: string;
  modalidade: string;
  data_publicacao: string;
  data_abertura: string | null;
  link_pncp: string;
  pncp_id: string;
}

export interface AlertasData {
  sector_id: string;
  sector_name: string;
  uf: string;
  bids: AlertaBid[];
  total: number;
  last_updated: string;
}

export interface ContratosSetorTopEntry {
  nome: string;
  cnpj: string;
  total_contratos: number;
  valor_total: number;
}

export interface ContratosSetorUfEntry {
  uf: string;
  total_contratos: number;
  valor_total: number;
}

export interface ContratosSetorTrend {
  month: string;
  count: number;
  value: number;
}

export interface ContratosSetorStats {
  sector_id: string;
  sector_name: string;
  total_contracts: number;
  total_value: number;
  avg_value: number;
  top_orgaos: ContratosSetorTopEntry[];
  top_fornecedores: ContratosSetorTopEntry[];
  monthly_trend: ContratosSetorTrend[];
  by_uf: ContratosSetorUfEntry[];
  last_updated: string;
}

// ---------------------------------------------------------------------------
// Static params generators
// ---------------------------------------------------------------------------

export function generateSectorParams(): { setor: string }[] {
  return SECTORS.map((s) => ({ setor: s.slug }));
}

export function generateSectorUfParams(): { setor: string; uf: string }[] {
  const params: { setor: string; uf: string }[] = [];
  for (const sector of SECTORS) {
    for (const uf of ALL_UFS) {
      params.push({ setor: sector.slug, uf: uf.toLowerCase() });
    }
  }
  return params;
}

export function generateLicitacoesParams(): { setor: string; uf: string }[] {
  return generateSectorUfParams();
}

export function getSectorFromSlug(slug: string): SectorMeta | undefined {
  return SECTORS.find((s) => s.slug === slug);
}

// ---------------------------------------------------------------------------
// Formatting utilities
// ---------------------------------------------------------------------------

export function formatBRL(value: number): string {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatBRLCompact(value: number): string {
  if (value >= 1_000_000_000) {
    return `R$${(value / 1_000_000_000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} bi`;
  }
  if (value >= 1_000_000) {
    return `R$${(value / 1_000_000).toLocaleString('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mi`;
  }
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

// ---------------------------------------------------------------------------
// Data fetching (server-side) — PSEO-P1-2048: migrado para fetchWithBudget
// ---------------------------------------------------------------------------

export async function fetchSectorBlogStats(sectorSlug: string): Promise<SectorBlogStats | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;

  const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
  return fetchWithBudget<SectorBlogStats>(
    `${backendUrl}/v1/blog/stats/setor/${sectorId}`,
    {
      timeout: 25000,
      retries: 1,
      revalidate: 3600,
      throwOn5xx: true,
      label: `blog-stats-${sectorId}`,
    },
  );
}

export async function fetchSectorUfBlogStats(
  sectorSlug: string,
  uf: string,
): Promise<SectorUfStats | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;

  const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
  return fetchWithBudget<SectorUfStats>(
    `${backendUrl}/v1/blog/stats/setor/${sectorId}/uf/${uf.toUpperCase()}`,
    {
      timeout: 25000,
      retries: 1,
      revalidate: 3600,
      throwOn5xx: true,
      label: `blog-stats-${sectorId}-${uf}`,
    },
  );
}

export async function fetchPanoramaStats(sectorSlug: string): Promise<PanoramaStats | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;

  const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
  return fetchWithBudget<PanoramaStats>(
    `${backendUrl}/v1/blog/stats/panorama/${sectorId}`,
    {
      timeout: 25000,
      retries: 1,
      revalidate: 3600,
      throwOn5xx: true,
      label: `panorama-${sectorId}`,
    },
  );
}

export async function fetchAlertasPublicos(
  sectorSlug: string,
  uf: string,
): Promise<AlertasData | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;

  const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
  return fetchWithBudget<AlertasData>(
    `${backendUrl}/v1/alertas/${sectorId}/uf/${uf.toUpperCase()}`,
    {
      timeout: 25000,
      retries: 1,
      revalidate: 3600,
      throwOn5xx: true,
      label: `alertas-${sectorId}-${uf}`,
    },
  );
}

export async function fetchContratosSetorStats(sectorSlug: string): Promise<ContratosSetorStats | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    Sentry.addBreadcrumb({
      category: 'fetch',
      message: 'fetchContratosSetorStats no BACKEND_URL',
      level: 'warning',
      data: { sector_slug: sectorSlug, outcome: 'no_backend_url' },
    });
    return null;
  }

  const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
  return fetchWithBudget<ContratosSetorStats>(
    `${backendUrl}/v1/blog/stats/contratos/${sectorId}`,
    {
      timeout: 25000,
      retries: 1,
      revalidate: 3600,
      throwOn5xx: true,
      label: `contratos-stats-${sectorId}`,
    },
  );
}
