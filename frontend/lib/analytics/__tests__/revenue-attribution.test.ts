/**
 * Tests for revenue attribution model (lib/analytics/revenue-attribution.ts).
 * CONV-009 (#1318)
 *
 * Verifies:
 * - storeRevenueEvent and getStoredRevenueEvents round-trip
 * - computeRevenueMetrics aggregates correctly
 * - computeRPM formula
 * - computeLeadsPerPage ratio
 * - computeConversionRate calculation
 * - computeUnlockRate calculation
 * - computeCheckoutCompletionRate calculation
 * - formatRate formatting
 * - SSR-safe: no-op when window is undefined
 */

import {
  storeRevenueEvent,
  getStoredRevenueEvents,
  computeRevenueMetrics,
  computeRPM,
  computeLeadsPerPage,
  computeConversionRate,
  computeUnlockRate,
  computeCheckoutCompletionRate,
  formatRate,
  type RevenueAttributionRow,
} from '../revenue-attribution';

const STORAGE_KEY = 'smartlic_revenue_attribution';

beforeEach(() => {
  // Clear jsdom's built-in sessionStorage between tests
  if (typeof window !== 'undefined' && window.sessionStorage) {
    window.sessionStorage.clear();
  }
});

// =========================================================================
// SSR safety
// =========================================================================

describe('SSR safety', () => {
  it('returns empty array when window is undefined', () => {
    const originalWindow = global.window;
    // @ts-expect-error intentional SSR simulation
    delete global.window;
    expect(getStoredRevenueEvents()).toEqual([]);
    global.window = originalWindow;
  });

  it('does not throw when storing with window undefined', () => {
    const originalWindow = global.window;
    // @ts-expect-error intentional SSR simulation
    delete global.window;
    expect(() =>
      storeRevenueEvent({
        revenue_type: 'subscription_new',
        amount_cents: 4990,
        currency: 'BRL',
        timestamp: new Date().toISOString(),
      }),
    ).not.toThrow();
    global.window = originalWindow;
  });
});

// =========================================================================
// Storage round-trip
// =========================================================================

describe('storage round-trip', () => {
  it('stores and retrieves a revenue event', () => {
    const event: RevenueAttributionRow = {
      revenue_type: 'subscription_new',
      amount_cents: 4990,
      currency: 'BRL',
      timestamp: '2026-06-01T00:00:00.000Z',
      template: 'fornecedor_page',
      intent_cluster: 'fornecedor',
      query_origin: 'fornecedor de asfalto',
      product: 'smartlic-mensal',
      transaction_id: 'txn-001',
    };

    storeRevenueEvent(event);
    const stored = getStoredRevenueEvents();

    expect(stored).toHaveLength(1);
    expect(stored[0]).toEqual(event);
  });

  it('stores multiple events and returns them in order', () => {
    storeRevenueEvent({
      revenue_type: 'microtransaction',
      amount_cents: 990,
      currency: 'BRL',
      timestamp: '2026-06-01T00:00:00.000Z',
    });
    storeRevenueEvent({
      revenue_type: 'subscription_new',
      amount_cents: 4990,
      currency: 'BRL',
      timestamp: '2026-06-01T01:00:00.000Z',
    });

    const stored = getStoredRevenueEvents();
    expect(stored).toHaveLength(2);
  });

  it('returns empty array when storage is empty', () => {
    expect(getStoredRevenueEvents()).toEqual([]);
  });

  it('handles invalid JSON in storage gracefully', () => {
    window.sessionStorage.setItem(STORAGE_KEY, 'invalid-json');
    expect(getStoredRevenueEvents()).toEqual([]);
  });

  it('caps storage at 500 events', () => {
    const event: RevenueAttributionRow = {
      revenue_type: 'microtransaction',
      amount_cents: 100,
      currency: 'BRL',
      timestamp: '2026-06-01T00:00:00.000Z',
    };

    // Store 510 events
    for (let i = 0; i < 510; i++) {
      storeRevenueEvent(event);
    }

    const stored = getStoredRevenueEvents();
    expect(stored).toHaveLength(500);
  });

  it('persists data in sessionStorage', () => {
    storeRevenueEvent({
      revenue_type: 'subscription_new',
      amount_cents: 4990,
      currency: 'BRL',
      timestamp: '2026-06-01T00:00:00.000Z',
    });

    const rawData = window.sessionStorage.getItem(STORAGE_KEY);
    expect(rawData).not.toBeNull();
    const parsed = JSON.parse(rawData!);
    expect(parsed).toHaveLength(1);
    expect(parsed[0].amount_cents).toBe(4990);
  });
});

// =========================================================================
// computeRevenueMetrics
// =========================================================================

describe('computeRevenueMetrics', () => {
  it('returns zero metrics for empty events', () => {
    const metrics = computeRevenueMetrics([]);
    expect(metrics.total_revenue_brl).toBe(0);
    expect(metrics.event_count).toBe(0);
    expect(metrics.by_template).toEqual({});
    expect(metrics.by_intent_cluster).toEqual({});
    expect(metrics.by_query_origin).toEqual({});
  });

  it('aggregates total revenue correctly', () => {
    const events: RevenueAttributionRow[] = [
      { revenue_type: 'subscription_new', amount_cents: 4990, currency: 'BRL', timestamp: '2026-06-01T00:00:00.000Z', template: 'fornecedor_page', intent_cluster: 'fornecedor' },
      { revenue_type: 'microtransaction', amount_cents: 990, currency: 'BRL', timestamp: '2026-06-01T01:00:00.000Z', template: 'orgao_page', intent_cluster: 'orgao' },
    ];

    const metrics = computeRevenueMetrics(events);
    expect(metrics.total_revenue_brl).toBe((4990 + 990) / 100);
    expect(metrics.event_count).toBe(2);
  });

  it('breaks down revenue by template', () => {
    const events: RevenueAttributionRow[] = [
      { revenue_type: 'subscription_new', amount_cents: 4990, currency: 'BRL', timestamp: '2026-06-01T00:00:00.000Z', template: 'fornecedor_page' },
      { revenue_type: 'subscription_new', amount_cents: 990, currency: 'BRL', timestamp: '2026-06-01T01:00:00.000Z', template: 'fornecedor_page' },
      { revenue_type: 'subscription_new', amount_cents: 2990, currency: 'BRL', timestamp: '2026-06-01T02:00:00.000Z', template: 'orgao_page' },
    ];

    const metrics = computeRevenueMetrics(events);
    expect(metrics.by_template['fornecedor_page']).toBe(4990 + 990);
    expect(metrics.by_template['orgao_page']).toBe(2990);
  });

  it('breaks down revenue by intent_cluster and query_origin', () => {
    const events: RevenueAttributionRow[] = [
      { revenue_type: 'subscription_new', amount_cents: 4990, currency: 'BRL', timestamp: '2026-06-01T00:00:00.000Z', intent_cluster: 'fornecedor', query_origin: 'fornecedor de asfalto' },
      { revenue_type: 'subscription_new', amount_cents: 2990, currency: 'BRL', timestamp: '2026-06-01T01:00:00.000Z', intent_cluster: 'orgao', query_origin: 'orgao publico sc' },
    ];

    const metrics = computeRevenueMetrics(events);
    expect(metrics.by_intent_cluster['fornecedor']).toBe(4990);
    expect(metrics.by_intent_cluster['orgao']).toBe(2990);
    expect(metrics.by_query_origin['fornecedor de asfalto']).toBe(4990);
    expect(metrics.by_query_origin['orgao publico sc']).toBe(2990);
  });

  it('ignores events without template/intent/query in breakdowns', () => {
    const events: RevenueAttributionRow[] = [
      { revenue_type: 'subscription_new', amount_cents: 4990, currency: 'BRL', timestamp: '2026-06-01T00:00:00.000Z' },
    ];

    const metrics = computeRevenueMetrics(events);
    expect(metrics.by_template).toEqual({});
    expect(metrics.by_intent_cluster).toEqual({});
    expect(metrics.by_query_origin).toEqual({});
    expect(metrics.total_revenue_brl).toBe(49.9);
  });
});

// =========================================================================
// computeRPM
// =========================================================================

describe('computeRPM', () => {
  it('computes RPM correctly', () => {
    // R$49.90 / 1000 impressions * 1000 = R$49.90
    const rpm = computeRPM(4990, 1000);
    expect(rpm).toBe(49.9);
  });

  it('returns 0 when revenue is 0', () => {
    expect(computeRPM(0, 1000)).toBe(0);
  });

  it('returns 0 when impressions is 0', () => {
    expect(computeRPM(4990, 0)).toBe(0);
  });

  it('returns 0 when impressions is negative', () => {
    expect(computeRPM(4990, -1)).toBe(0);
  });
});

// =========================================================================
// computeLeadsPerPage
// =========================================================================

describe('computeLeadsPerPage', () => {
  it('computes leads per page correctly', () => {
    // 5 leads / 100 pages = 0.05
    const lpp = computeLeadsPerPage(5, 100);
    expect(lpp).toBe(0.05);
  });

  it('returns 0 when leads is 0', () => {
    expect(computeLeadsPerPage(0, 100)).toBe(0);
  });

  it('returns 0 when page count is 0', () => {
    expect(computeLeadsPerPage(5, 0)).toBe(0);
  });
});

// =========================================================================
// computeConversionRate
// =========================================================================

describe('computeConversionRate', () => {
  it('computes conversion rate correctly', () => {
    // 1.23 conversions / 100 visits = 0.0123
    const rate = computeConversionRate(1.23, 100);
    expect(rate).toBe(0.0123);
  });

  it('returns 0 when conversions is 0', () => {
    expect(computeConversionRate(0, 100)).toBe(0);
  });

  it('returns 0 when visits is 0', () => {
    expect(computeConversionRate(5, 0)).toBe(0);
  });
});

// =========================================================================
// computeUnlockRate
// =========================================================================

describe('computeUnlockRate', () => {
  it('computes unlock rate correctly', () => {
    // 15 completed / 100 attempts = 0.15
    const rate = computeUnlockRate(15, 100);
    expect(rate).toBe(0.15);
  });

  it('returns 0 when completed is 0', () => {
    expect(computeUnlockRate(0, 100)).toBe(0);
  });

  it('returns 0 when attempts is 0', () => {
    expect(computeUnlockRate(15, 0)).toBe(0);
  });
});

// =========================================================================
// computeCheckoutCompletionRate
// =========================================================================

describe('computeCheckoutCompletionRate', () => {
  it('computes checkout completion rate correctly', () => {
    // 60 completed / 100 started = 0.60
    const rate = computeCheckoutCompletionRate(60, 100);
    expect(rate).toBe(0.6);
  });

  it('returns 0 when completed is 0', () => {
    expect(computeCheckoutCompletionRate(0, 100)).toBe(0);
  });

  it('returns 0 when started is 0', () => {
    expect(computeCheckoutCompletionRate(60, 0)).toBe(0);
  });
});

// =========================================================================
// formatRate
// =========================================================================

describe('formatRate', () => {
  it('formats 0.0123 as "1.23%"', () => {
    expect(formatRate(0.0123)).toBe('1.23%');
  });

  it('formats 1 as "100.00%"', () => {
    expect(formatRate(1)).toBe('100.00%');
  });

  it('returns "0%" for 0', () => {
    expect(formatRate(0)).toBe('0%');
  });

  it('returns "0%" for negative values', () => {
    expect(formatRate(-1)).toBe('0%');
  });
});
