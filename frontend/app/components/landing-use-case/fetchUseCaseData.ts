/**
 * fetchUseCaseData — DataLake data fetching helpers for use-case landing pages
 *
 * Fetches real data from public backend endpoints at ISR revalidation time.
 * Every fetch has a fallback path: returns null on error rather than crashing the page.
 */
import { ssgLimitedFetch } from '@/lib/concurrency';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SectorStatsRaw {
  sector_id: string;
  sector_name: string;
  sector_description: string;
  slug: string;
  total_open: number;
  total_value: number;
  avg_value: number;
  top_ufs: { name: string; count: number }[];
  top_modalidades: { name: string; count: number }[];
  sample_items: {
    titulo: string;
    orgao: string;
    valor: number | null;
    uf: string;
    data: string;
  }[];
  last_updated: string;
}

export interface ContractStatsRaw {
  sector_id: string;
  sector_name: string;
  uf: string;
  total_contracts: number;
  total_value: number;
  avg_value: number;
  top_orgaos: { nome: string; cnpj: string; total_contratos: number; valor_total: number }[];
  top_fornecedores: { nome: string; cnpj: string; total_contratos: number; valor_total: number }[];
  monthly_trend: { month: string; count: number; value: number }[];
  sample_contracts: {
    objeto: string;
    orgao: string;
    fornecedor: string;
    valor: number | null;
    data_assinatura: string;
  }[];
  last_updated: string;
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

/**
 * Fetch sector stats from public endpoint.
 * Returns null on error (graceful degradation).
 */
export async function fetchSectorStats(slug: string): Promise<SectorStatsRaw | null> {
  try {
    const res = await ssgLimitedFetch(
      `${BACKEND_URL}/v1/sectors/${slug}/stats`,
      {
        next: { revalidate: 3600 },
        signal: AbortSignal.timeout(10000),
      },
    );
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Fetch contract stats for a sector + UF.
 * Returns null on error (graceful degradation).
 */
export async function fetchContractStats(
  sector: string,
  uf: string,
): Promise<ContractStatsRaw | null> {
  try {
    const res = await ssgLimitedFetch(
      `${BACKEND_URL}/v1/contratos/${sector}/${uf}/stats`,
      {
        next: { revalidate: 3600 },
        signal: AbortSignal.timeout(10000),
      },
    );
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Fetch fornecedores (suppliers) stats for a sector + UF.
 * Returns null on error.
 */
export async function fetchFornecedoresStats(
  sector: string,
  uf: string,
): Promise<ContractStatsRaw | null> {
  try {
    const res = await ssgLimitedFetch(
      `${BACKEND_URL}/v1/fornecedores/${sector}/${uf}/stats`,
      {
        next: { revalidate: 3600 },
        signal: AbortSignal.timeout(10000),
      },
    );
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

/**
 * Format a numeric value as BRL currency string.
 */
export function formatBRL(value: number | null | undefined): string {
  if (value == null) return 'N/A';
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
    maximumFractionDigits: 0,
  }).format(value);
}
