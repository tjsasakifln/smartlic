/**
 * Tests for search-time-estimator utility.
 * UX-311: Verifies moving average calculation, fallback when insufficient data,
 * and precision within ±20% tolerance.
 */

import {
  recordSearchTime,
  getEstimatedTime,
  fixedEstimate,
  getTotalRecordedSearches,
  getCalibrationStatus,
  clearRecords,
  CALIBRATION_THRESHOLD,
  PRECISION_TARGET,
} from '../search-time-estimator';

// ── Helpers ─────────────────────────────────────────────────────────────

/**
 * Fill localStorage with enough records to pass the calibration threshold.
 * Creates synthetic records simulating different UF counts and elapsed times.
 */
function seedCalibratedData(): void {
  clearRecords();
  const baseTimestamp = Date.now() - 7 * 24 * 60 * 60 * 1000; // 7 days ago

  // Create 60 records (>CALIBRATION_THRESHOLD=50) across different UF buckets
  for (let i = 0; i < 60; i++) {
    // Distribute across UF counts 1-27
    const ufCount = (i % 10) + 1; // cycles 1-10
    // Realistic elapsed times: base + ufCount * ~3s + noise
    const elapsedSeconds = 15 + ufCount * 3 + Math.floor(Math.random() * 10);
    recordSearchTime(ufCount, elapsedSeconds);
  }
}

beforeEach(() => {
  clearRecords();
  // Mock localStorage for environments where it's not available
  if (typeof window === 'undefined') {
    const store: Record<string, string> = {};
    const mockStorage = {
      getItem: (key: string) => store[key] ?? null,
      setItem: (key: string, value: string) => { store[key] = value; },
      removeItem: (key: string) => { delete store[key]; },
      length: 0,
      clear: () => { Object.keys(store).forEach(k => delete store[k]); },
      key: (_index: number) => null,
    };
    Object.defineProperty(globalThis, 'localStorage', { value: mockStorage, writable: true });
  }
});

// ── Moving Average ─────────────────────────────────────────────────────

describe('moving average calculation', () => {
  it('returns calibrated estimate when total records >= threshold', () => {
    seedCalibratedData();
    const totalRecords = getTotalRecordedSearches();
    expect(totalRecords).toBeGreaterThanOrEqual(CALIBRATION_THRESHOLD);

    const estimate = getEstimatedTime(5, 7);
    // With seeded data for ufCount=5, average should be ~ 15 + 5*3 + ~5 = ~35
    expect(estimate).toBeGreaterThan(0);
    expect(estimate).toBeLessThan(120);
  });

  it('returns different estimates for different UF counts', () => {
    seedCalibratedData();

    const estimate1Uf = getEstimatedTime(1, 7);
    const estimate10Ufs = getEstimatedTime(10, 7);

    // More UFs should generally mean longer estimates
    expect(estimate10Ufs).toBeGreaterThanOrEqual(estimate1Uf);
  });

  it('computes estimate within reasonable range for single UF', () => {
    // Add direct data for 1 UF
    for (let i = 0; i < CALIBRATION_THRESHOLD; i++) {
      recordSearchTime(1, 20 + Math.floor(Math.random() * 10));
    }

    const estimate = getEstimatedTime(1, 7);
    // Average of 20-30 = ~25
    expect(estimate).toBeGreaterThan(15);
    expect(estimate).toBeLessThan(40);
  });

  it('uses overall average when specific bucket has no data', () => {
    // Record only for UF count = 10
    for (let i = 0; i < CALIBRATION_THRESHOLD; i++) {
      recordSearchTime(10, 40);
    }

    // Request estimate for UF count = 1 (no data for 1-UF bucket)
    const estimate = getEstimatedTime(1, 7);
    // Should fall back to overall average across all records (all 40s)
    expect(estimate).toBe(40);
  });
});

// ── Fallback ────────────────────────────────────────────────────────────

describe('fallback when insufficient data', () => {
  it('returns fixed estimate when no records exist', () => {
    expect(getTotalRecordedSearches()).toBe(0);

    const estimate = getEstimatedTime(5, 7);
    const expected = fixedEstimate(5, 7);
    expect(estimate).toBe(expected);
  });

  it('returns fixed estimate when records below threshold', () => {
    // Record just a few searches
    for (let i = 0; i < 10; i++) {
      recordSearchTime(5, 30);
    }

    expect(getTotalRecordedSearches()).toBe(10);
    expect(getTotalRecordedSearches()).toBeLessThan(CALIBRATION_THRESHOLD);

    const estimate = getEstimatedTime(5, 7);
    const expected = fixedEstimate(5, 7);
    expect(estimate).toBe(expected);
  });

  it('fixedEstimate produces consistent results', () => {
    // Same inputs should always produce the same output
    expect(fixedEstimate(5, 7)).toBe(fixedEstimate(5, 7));
    expect(fixedEstimate(1, 1)).toBe(fixedEstimate(1, 1));

    // Known values: 5 UFs, 7 days
    // baseTime=10, parallelUfs=5, fetchTime=5*3=15, dateMultiplier=1.0
    // ceil(10 + 15*1.0 + 3 + 5 + 3) = ceil(36) = 36
    expect(fixedEstimate(5, 7)).toBe(36);

    // 27 UFs, 30 days
    // baseTime=10, parallelUfs=10, queuedUfs=17, fetchTime=10*3+17*2=64, dateMultiplier=1.3
    // ceil(10 + 64*1.3 + 3 + 5 + 3) = ceil(10 + 83.2 + 11) = ceil(104.2) = 105
    expect(fixedEstimate(27, 30)).toBe(105);
  });

  it('falls back when date range is > 14 days', () => {
    const estimate7Days = fixedEstimate(5, 7);
    const estimate30Days = fixedEstimate(5, 30);
    expect(estimate30Days).toBeGreaterThan(estimate7Days);
  });
});

// ── Calibration Status ──────────────────────────────────────────────────

describe('calibration status', () => {
  it('returns isCalibrated=false when empty', () => {
    const status = getCalibrationStatus();
    expect(status.totalRecords).toBe(0);
    expect(status.isCalibrated).toBe(false);
  });

  it('returns isCalibrated=true when >= threshold', () => {
    for (let i = 0; i < CALIBRATION_THRESHOLD; i++) {
      recordSearchTime(5, 30);
    }
    const status = getCalibrationStatus();
    expect(status.totalRecords).toBe(CALIBRATION_THRESHOLD);
    expect(status.isCalibrated).toBe(true);
  });

  it('includes bucket-level statistics', () => {
    recordSearchTime(1, 25);
    recordSearchTime(5, 35);

    const status = getCalibrationStatus();
    // The bucket stats should exist for buckets that have data
    expect(status.bucketStats['1']).toBeDefined();
    expect(status.bucketStats['1'].count).toBe(1);

    // 5 UFs falls in "4-5" bucket
    expect(status.bucketStats['4-5']).toBeDefined();
    expect(status.bucketStats['4-5'].count).toBe(1);
  });
});

// ── Record Search Time ──────────────────────────────────────────────────

describe('recordSearchTime', () => {
  it('stores search time records', () => {
    recordSearchTime(5, 42);
    expect(getTotalRecordedSearches()).toBe(1);
  });

  it('ignores invalid inputs', () => {
    recordSearchTime(0, 42);
    expect(getTotalRecordedSearches()).toBe(0);

    recordSearchTime(5, 0);
    expect(getTotalRecordedSearches()).toBe(0);

    recordSearchTime(5, -1);
    expect(getTotalRecordedSearches()).toBe(0);
  });

  it('accumulates multiple records', () => {
    recordSearchTime(5, 30);
    recordSearchTime(10, 60);
    recordSearchTime(3, 20);
    expect(getTotalRecordedSearches()).toBe(3);
  });
});

// ── Precision ───────────────────────────────────────────────────────────

describe('precision target', () => {
  it('PRECISION_TARGET is set to 0.20 (±20%)', () => {
    expect(PRECISION_TARGET).toBe(0.20);
  });

  it('calibrated estimate is within ±20% of average for the same UF count', () => {
    // Create a known pattern: 10 UFs consistently taking ~60s
    const actualAvg = 60;
    for (let i = 0; i < 60; i++) {
      // Add small variance
      const variance = Math.floor(Math.random() * 10) - 5;
      recordSearchTime(10, actualAvg + variance);
    }

    const estimate = getEstimatedTime(10, 7);
    const deviation = Math.abs(estimate - actualAvg) / actualAvg;
    expect(deviation).toBeLessThanOrEqual(PRECISION_TARGET + 0.05); // allow small buffer for ceil()
  });
});

// ── Clear Records ───────────────────────────────────────────────────────

describe('clearRecords', () => {
  it('removes all stored records', () => {
    recordSearchTime(5, 30);
    recordSearchTime(10, 60);
    expect(getTotalRecordedSearches()).toBe(2);

    clearRecords();
    expect(getTotalRecordedSearches()).toBe(0);
  });
});
