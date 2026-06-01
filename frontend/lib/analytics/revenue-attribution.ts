/**
 * CONV-009 (#1318): Revenue attribution model.
 *
 * Links revenue events to template, intent_cluster, and query_origin so
 * downstream dashboards can compute:
 *   - Receita por mil impressoes organicas
 *   - Receita por template / intent_cluster / query
 *   - RPM (revenue per mille) for programmatic pages
 *
 * All functions are SSR-safe and never throw.
 *
 * Import pattern:
 *   import { computeRevenueMetrics } from '@/lib/analytics/revenue-attribution';
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type RevenueEventType =
  | 'microtransaction'
  | 'subscription_new'
  | 'subscription_renewal'
  | 'subscription_upgrade';

export interface RevenueAttributionRow {
  /** Revenue event subtype */
  revenue_type: RevenueEventType;
  /** Revenue amount in BRL cents */
  amount_cents: number;
  /** Currency code */
  currency: string;
  /** ISO timestamp */
  timestamp: string;
  /** Template/slug attribution */
  template?: string;
  /** Intent cluster attribution */
  intent_cluster?: string;
  /** GSC query origin when available */
  query_origin?: string;
  /** UTM source */
  utm_source?: string;
  /** UTM campaign */
  utm_campaign?: string;
  /** Product or plan name */
  product?: string;
  /** Transaction or invoice ID */
  transaction_id?: string;
}

export interface RevenueMetrics {
  /** Total revenue in BRL */
  total_revenue_brl: number;
  /** Revenue by source template */
  by_template: Record<string, number>;
  /** Revenue by intent cluster */
  by_intent_cluster: Record<string, number>;
  /** Revenue by query origin (GSC) */
  by_query_origin: Record<string, number>;
  /** Number of revenue events */
  event_count: number;
}

// ---------------------------------------------------------------------------
// Storage key
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'smartlic_revenue_attribution';

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Retrieve stored revenue attribution events from sessionStorage.
 * Used to compute revenue metrics on the client.
 * SSR-safe — returns empty array when window is unavailable.
 */
export function getStoredRevenueEvents(): RevenueAttributionRow[] {
  if (typeof window === 'undefined') return [];
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    return stored ? (JSON.parse(stored) as RevenueAttributionRow[]) : [];
  } catch {
    return [];
  }
}

/**
 * Append a revenue attribution event to sessionStorage.
 * Maintains a running log of revenue events for client-side analytics.
 * SSR-safe — no-op when window is unavailable.
 */
export function storeRevenueEvent(event: RevenueAttributionRow): void {
  if (typeof window === 'undefined') return;
  try {
    const existing = getStoredRevenueEvents();
    existing.push(event);
    // Cap storage at 500 events to avoid quota issues
    const trimmed = existing.slice(-500);
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(trimmed));
  } catch {
    // sessionStorage may be full or unavailable — swallow silently
  }
}

/**
 * Compute aggregate revenue metrics from stored events.
 * Returns total revenue (in BRL), breakdowns by template, intent_cluster,
 * and query_origin, plus event count.
 */
export function computeRevenueMetrics(events?: RevenueAttributionRow[]): RevenueMetrics {
  const rows = events ?? getStoredRevenueEvents();

  const byTemplate: Record<string, number> = {};
  const byIntent: Record<string, number> = {};
  const byQuery: Record<string, number> = {};

  let totalCents = 0;

  for (const row of rows) {
    totalCents += row.amount_cents;

    if (row.template) {
      byTemplate[row.template] = (byTemplate[row.template] ?? 0) + row.amount_cents;
    }
    if (row.intent_cluster) {
      byIntent[row.intent_cluster] = (byIntent[row.intent_cluster] ?? 0) + row.amount_cents;
    }
    if (row.query_origin) {
      byQuery[row.query_origin] = (byQuery[row.query_origin] ?? 0) + row.amount_cents;
    }
  }

  return {
    total_revenue_brl: totalCents / 100,
    by_template: byTemplate,
    by_intent_cluster: byIntent,
    by_query_origin: byQuery,
    event_count: rows.length,
  };
}

/**
 * Compute revenue per mille (RPM) for a given template.
 *
 * RPM = (revenue_from_template / impressions) * 1000
 *
 * @param revenueCents - Revenue in BRL cents attributed to the template
 * @param impressions  - Number of organic impressions for the template
 * @returns Revenue per mille in BRL (rounded to 2 decimal places), or 0 if impressions is 0
 */
export function computeRPM(revenueCents: number, impressions: number): number {
  if (impressions <= 0 || revenueCents <= 0) return 0;
  const revenueBRL = revenueCents / 100;
  return Math.round((revenueBRL / impressions) * 1000 * 100) / 100;
}

/**
 * Compute leads-per-page ratio for programmatic pages.
 *
 * @param leadsFromPseo - Number of leads attributed to pSEO pages
 * @param pseoPageCount - Number of indexed pSEO pages
 * @returns Leads per page ratio (rounded to 4 decimal places), or 0 if page count is 0
 */
export function computeLeadsPerPage(leadsFromPseo: number, pseoPageCount: number): number {
  if (pseoPageCount <= 0 || leadsFromPseo <= 0) return 0;
  return Math.round((leadsFromPseo / pseoPageCount) * 10000) / 10000;
}

/**
 * Compute conversion rate per intent cluster.
 *
 * @param conversions - Number of conversions for the cluster
 * @param visits      - Number of visits for the cluster
 * @returns Conversion rate as a decimal (e.g. 0.0123 for 1.23%), or 0
 */
export function computeConversionRate(conversions: number, visits: number): number {
  if (visits <= 0 || conversions <= 0) return 0;
  return Math.round((conversions / visits) * 10000) / 10000;
}

/**
 * Compute unlock rate: preview_unlock_complete / preview_unlock_attempt
 *
 * @param completed - Number of successful preview unlocks
 * @param attempts  - Number of preview unlock attempts
 * @returns Unlock rate as a decimal (e.g. 0.15 for 15%), or 0
 */
export function computeUnlockRate(completed: number, attempts: number): number {
  if (attempts <= 0 || completed <= 0) return 0;
  return Math.round((completed / attempts) * 10000) / 10000;
}

/**
 * Compute checkout completion rate: checkout_complete / checkout_start
 *
 * @param completed - Number of completed checkouts
 * @param started   - Number of checkout starts
 * @returns Checkout completion rate as a decimal, or 0
 */
export function computeCheckoutCompletionRate(completed: number, started: number): number {
  if (started <= 0 || completed <= 0) return 0;
  return Math.round((completed / started) * 10000) / 10000;
}

/**
 * Format a rate as a percentage string, e.g. 0.0123 -> "1.23%".
 * Returns "0%" for zero/negative input.
 */
export function formatRate(rate: number): string {
  if (rate <= 0) return '0%';
  return `${(rate * 100).toFixed(2)}%`;
}
