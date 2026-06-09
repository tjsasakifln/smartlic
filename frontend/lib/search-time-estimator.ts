/**
 * search-time-estimator — Moving-average calibration for search time estimates.
 *
 * UX-311: Replaces hardcoded estimate formula with a moving average of real
 * search latencies, bucketed by UF count. Falls back to fixed formula when
 * insufficient data (< CALIBRATION_THRESHOLD total searches).
 *
 * ## Storage
 * - localStorage key: `search_time_log`
 * - Schema: Array of `SearchTimeRecord` objects
 * - Max entries: unbounded (pruned by age, not count)
 *
 * ## Calibration
 * - Threshold: 50 total recorded searches before calibrated estimates are used
 * - Precision target: ±20% of actual time
 * - Bucketing: by UF count (1, 2-3, 4-5, 6-10, 11-20, 21-27)
 */

// ── Types ───────────────────────────────────────────────────────────────

export interface SearchTimeRecord {
  /** Number of UFs selected in this search */
  ufCount: number;
  /** Elapsed time in seconds */
  elapsedSeconds: number;
  /** Unix timestamp of when the search completed */
  timestamp: number;
}

// ── Constants ───────────────────────────────────────────────────────────

const STORAGE_KEY = 'search_time_log';

/**
 * Minimum total records across all UF buckets before calibrated estimates
 * are preferred over the fixed fallback formula.
 */
export const CALIBRATION_THRESHOLD = 50;

/**
 * Precision target: calibrated estimate should be within ±20% of actual.
 * Used for validation but does not gate estimate selection.
 */
export const PRECISION_TARGET = 0.20;

// ── UF Buckets ──────────────────────────────────────────────────────────

interface BucketDef {
  label: string;
  minUf: number;
  maxUf: number;
}

const UF_BUCKETS: BucketDef[] = [
  { label: '1', minUf: 1, maxUf: 1 },
  { label: '2-3', minUf: 2, maxUf: 3 },
  { label: '4-5', minUf: 4, maxUf: 5 },
  { label: '6-10', minUf: 6, maxUf: 10 },
  { label: '11-20', minUf: 11, maxUf: 20 },
  { label: '21-27', minUf: 21, maxUf: 27 },
];

function getBucketForUfCount(ufCount: number): BucketDef {
  for (const bucket of UF_BUCKETS) {
    if (ufCount >= bucket.minUf && ufCount <= bucket.maxUf) {
      return bucket;
    }
  }
  // Fallback: 27 UFs (all Brazil)
  return UF_BUCKETS[UF_BUCKETS.length - 1];
}

// ── Fixed fallback formula (same as original estimateSearchTimeFn) ───────

/**
 * Fallback estimate when calibration data is insufficient.
 * Mirrors the original hardcoded formula.
 */
export function fixedEstimate(ufCount: number, dateRangeDays: number): number {
  const baseTime = 10;
  const parallelUfs = Math.min(ufCount, 10);
  const queuedUfs = Math.max(0, ufCount - 10);
  const fetchTime = parallelUfs * 3 + queuedUfs * 2;
  const dateMultiplier = dateRangeDays > 14 ? 1.3 : dateRangeDays > 7 ? 1.1 : 1.0;
  return Math.ceil(baseTime + fetchTime * dateMultiplier + 3 + 5 + 3);
}

// ── Storage I/O ─────────────────────────────────────────────────────────

function loadRecords(): SearchTimeRecord[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed as SearchTimeRecord[];
  } catch {
    return [];
  }
}

function saveRecords(records: SearchTimeRecord[]): void {
  if (typeof window === 'undefined') return;
  try {
    // Prune records older than 90 days to keep storage bounded
    const cutoff = Date.now() - 90 * 24 * 60 * 60 * 1000;
    const pruned = records.filter(r => r.timestamp > cutoff);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pruned));
  } catch {
    // localStorage quota exceeded — silently degrade
  }
}

// ── Public API ──────────────────────────────────────────────────────────

/**
 * Record a completed search time for calibration.
 * Call this when a search finishes (result received, loading = false).
 *
 * @param ufCount - Number of UFs selected
 * @param elapsedSeconds - Actual elapsed time in seconds
 */
export function recordSearchTime(ufCount: number, elapsedSeconds: number): void {
  if (ufCount <= 0 || elapsedSeconds <= 0) return;

  const records = loadRecords();
  records.push({
    ufCount,
    elapsedSeconds,
    timestamp: Date.now(),
  });
  saveRecords(records);
}

/**
 * Get calibrated estimate based on moving average per UF bucket.
 * Falls back to fixed formula when total records < CALIBRATION_THRESHOLD
 * or when the specific bucket has no data.
 *
 * @param ufCount - Number of UFs selected
 * @param dateRangeDays - Date range in days (only used for fallback)
 * @returns Estimated time in seconds
 */
export function getEstimatedTime(ufCount: number, dateRangeDays: number): number {
  const records = loadRecords();
  const totalRecords = records.length;

  // Insufficient data — use fallback
  if (totalRecords < CALIBRATION_THRESHOLD) {
    return fixedEstimate(ufCount, dateRangeDays);
  }

  const bucket = getBucketForUfCount(ufCount);
  const bucketRecords = records.filter(
    r => r.ufCount >= bucket.minUf && r.ufCount <= bucket.maxUf
  );

  // If the specific bucket has no data, use the overall average
  if (bucketRecords.length === 0) {
    const overallAvg = records.reduce((sum, r) => sum + r.elapsedSeconds, 0) / records.length;
    return Math.ceil(overallAvg);
  }

  // Moving average for this bucket
  const totalSeconds = bucketRecords.reduce((sum, r) => sum + r.elapsedSeconds, 0);
  const avgSeconds = totalSeconds / bucketRecords.length;
  return Math.ceil(avgSeconds);
}

/**
 * Get total number of recorded searches across all UF buckets.
 */
export function getTotalRecordedSearches(): number {
  return loadRecords().length;
}

/**
 * Get calibration status info for debugging/monitoring.
 */
export function getCalibrationStatus(): {
  totalRecords: number;
  isCalibrated: boolean;
  bucketStats: Record<string, { count: number; avgSeconds: number }>;
} {
  const records = loadRecords();
  const bucketStats: Record<string, { count: number; avgSeconds: number }> = {};

  for (const bucket of UF_BUCKETS) {
    const bucketRecords = records.filter(
      r => r.ufCount >= bucket.minUf && r.ufCount <= bucket.maxUf
    );
    const avgSeconds = bucketRecords.length > 0
      ? bucketRecords.reduce((sum, r) => sum + r.elapsedSeconds, 0) / bucketRecords.length
      : 0;
    bucketStats[bucket.label] = {
      count: bucketRecords.length,
      avgSeconds: Math.ceil(avgSeconds),
    };
  }

  return {
    totalRecords: records.length,
    isCalibrated: records.length >= CALIBRATION_THRESHOLD,
    bucketStats,
  };
}

/**
 * Clear all recorded search times (for testing).
 */
export function clearRecords(): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // silently fail
  }
}
