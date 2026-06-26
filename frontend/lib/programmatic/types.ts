/**
 * PSEO-002: Tipos, constantes, utilitários e fetchers extraídos de lib/programmatic.ts.
 *
 * Fornece definições de tipo, mapeamentos setor↔slug, constantes de UF,
 * funções de formatação, geração de static params e data fetching.
 */
import * as Sentry from '@sentry/nextjs';
import { SECTORS, type SectorMeta } from '@/lib/sectors';
import { ssgLimitedFetch } from '@/lib/concurrency';

// ---------------------------------------------------------------------------
// Build phase detection
// ---------------------------------------------------------------------------

/**
 * Detecta se estamos em fase de build (next build) ou ISR runtime.
 *
 * Durante `next build`, static generation não tem cache ISR — throw 5xx é
 * fatal. Durante ISR runtime, throw em 5xx preserva o last-good cached page.
 *
 * Estratégia de detecção:
 *   1. NEXT_PHASE env var — definida pelo Next.js CLI no processo principal.
 *      Pode não propagar para worker processes que geram páginas estáticas.
 *   2. process.argv fallback — workers de build do Next.js são spawnados de
 *      next/dist/build/ ou next/dist/compiled/. Workers de ISR runtime usam
 *      next/dist/server/, que são excluídos.
 */
export const IS_BUILD_PHASE: boolean = (() => {
  if (typeof process === 'undefined') return false;
  if (
    process.env.NEXT_PHASE === 'phase-production-build' ||
    process.env.NEXT_PHASE === 'phase-development-build'
  ) {
    return true;
  }
  // Fallback: detecção via entry-point path do worker de build do Next.js.
  const execPath = process.argv[1] || '';
  if (
    execPath.includes('next/dist/build') ||
    execPath.includes('next/dist/compiled')
  ) {
    return true;
  }
  return false;
})();

// ---------------------------------------------------------------------------
// Sector slug ↔ backend ID mappings
// ---------------------------------------------------------------------------

/** Slugs cujo ID no backend difere do padrão slug.replace(/-/g, '_'). */
export const SECTOR_SLUG_TO_BACKEND_ID: Record<string, string> = {
  software: 'software_desenvolvimento',
  facilities: 'servicos_prediais',
  saude: 'medicamentos',
  transporte: 'transporte_servicos',
};

/** Reverse mapping — backend sector ID → frontend slug. */
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
  AC: 'Acre', AL: 'Alagoas', AM: 'Amazonas', AP: 'Amapá',
  BA: 'Bahia', CE: 'Ceará', DF: 'Distrito Federal', ES: 'Espírito Santo',
  GO: 'Goiás', MA: 'Maranhão', MG: 'Minas Gerais', MS: 'Mato Grosso do Sul',
  MT: 'Mato Grosso', PA: 'Pará', PB: 'Paraíba', PE: 'Pernambuco',
  PI: 'Piauí', PR: 'Paraná', RJ: 'Rio de Janeiro', RN: 'Rio Grande do Norte',
  RO: 'Rondônia', RR: 'Roraima', RS: 'Rio Grande do Sul', SC: 'Santa Catarina',
  SE: 'Sergipe', SP: 'São Paulo', TO: 'Tocantins',
};

export const UF_PREPOSITIONS: Record<string, string> = {
  AC: 'no', AL: 'em', AM: 'no', AP: 'no', BA: 'na', CE: 'no',
  DF: 'no', ES: 'no', GO: 'em', MA: 'no', MG: 'em', MS: 'no',
  MT: 'no', PA: 'no', PB: 'na', PE: 'em', PI: 'no', PR: 'no',
  RJ: 'no', RN: 'no', RO: 'em', RR: 'em', RS: 'no', SC: 'em',
  SE: 'em', SP: 'em', TO: 'no',
};

/** Retorna a preposição portuguesa correta para um estado brasileiro. */
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
// Data fetching (server-side)
// ---------------------------------------------------------------------------

export async function fetchSectorBlogStats(sectorSlug: string): Promise<SectorBlogStats | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;

  try {
    const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
    const res = await ssgLimitedFetch(`${backendUrl}/v1/blog/stats/setor/${sectorId}`, {
      signal: AbortSignal.timeout(25000),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function fetchSectorUfBlogStats(
  sectorSlug: string,
  uf: string,
): Promise<SectorUfStats | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;

  try {
    const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
    const res = await ssgLimitedFetch(`${backendUrl}/v1/blog/stats/setor/${sectorId}/uf/${uf.toUpperCase()}`, {
      signal: AbortSignal.timeout(25000),
    });
    if (res.status >= 500) {
      if (IS_BUILD_PHASE) {
        console.warn(`[programmatic] Backend 5xx (${res.status}) during build for ${sectorId}/${uf} — rendering fallback`);
        return null;
      }
      throw new Error(`blog_stats_backend_5xx:${res.status}`);
    }
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    if (err instanceof Error && err.message.startsWith('blog_stats_backend_5xx')) throw err;
    return null;
  }
}

export async function fetchPanoramaStats(sectorSlug: string): Promise<PanoramaStats | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;

  try {
    const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
    const res = await ssgLimitedFetch(`${backendUrl}/v1/blog/stats/panorama/${sectorId}`, {
      signal: AbortSignal.timeout(25000),
    });
    if (res.status >= 500) {
      if (IS_BUILD_PHASE) {
        console.warn(`[programmatic] Backend 5xx (${res.status}) during build for panorama/${sectorId} — rendering fallback`);
        return null;
      }
      throw new Error(`panorama_stats_backend_5xx:${res.status}`);
    }
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    if (err instanceof Error && err.message.startsWith('panorama_stats_backend_5xx')) throw err;
    return null;
  }
}

export async function fetchAlertasPublicos(
  sectorSlug: string,
  uf: string,
): Promise<AlertasData | null> {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) return null;

  try {
    const sectorId = SECTOR_SLUG_TO_BACKEND_ID[sectorSlug] ?? sectorSlug.replace(/-/g, '_');
    const res = await ssgLimitedFetch(`${backendUrl}/v1/alertas/${sectorId}/uf/${uf.toUpperCase()}`, {
      signal: AbortSignal.timeout(25000),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
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
  const url = `${backendUrl}/v1/blog/stats/contratos/${sectorId}`;

  try {
    const res = await ssgLimitedFetch(url, {
      signal: AbortSignal.timeout(25000),
    });

    if (res.status >= 500) {
      if (IS_BUILD_PHASE) {
        console.warn(`[programmatic] Backend 5xx during build for contratos/${sectorId} — rendering fallback`);
        Sentry.addBreadcrumb({
          category: 'fetch',
          message: `fetchContratosSetorStats 5xx (build phase)`,
          level: 'warning',
          data: { sector_slug: sectorSlug, sector_id: sectorId, status: res.status, outcome: 'build_5xx_fallback' },
        });
        return null;
      }
      Sentry.addBreadcrumb({
        category: 'fetch',
        message: `fetchContratosSetorStats 5xx (ISR throw)`,
        level: 'error',
        data: { sector_slug: sectorSlug, sector_id: sectorId, status: res.status, outcome: 'isr_5xx_throw' },
      });
      throw new Error(`contratos_setor_stats_backend_5xx:${res.status}`);
    }

    if (!res.ok) {
      Sentry.addBreadcrumb({
        category: 'fetch',
        message: `fetchContratosSetorStats HTTP ${res.status}`,
        level: 'warning',
        data: { sector_slug: sectorSlug, sector_id: sectorId, status: res.status, outcome: 'http_error_null' },
      });
      return null;
    }

    Sentry.addBreadcrumb({
      category: 'fetch',
      message: 'fetchContratosSetorStats success',
      level: 'info',
      data: { sector_slug: sectorSlug, sector_id: sectorId, status: res.status, outcome: 'success' },
    });
    return res.json();
  } catch (err) {
    if (err instanceof Error && err.message.startsWith('contratos_setor_stats_backend_5xx')) {
      Sentry.addBreadcrumb({
        category: 'fetch',
        message: `fetchContratosSetorStats re-throw 5xx`,
        level: 'error',
        data: { sector_slug: sectorSlug, sector_id: sectorId, outcome: '5xx_rethrow' },
      });
      throw err;
    }
    Sentry.addBreadcrumb({
      category: 'fetch',
      message: `fetchContratosSetorStats error`,
      level: 'error',
      data: { sector_slug: sectorSlug, sector_id: sectorId, outcome: 'catch_null', error: String(err) },
    });
    return null;
  }
}
