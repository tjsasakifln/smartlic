'use client';

import { useSearchParams } from 'next/navigation';
import {
  type IntentCluster,
  type DetectionSource,
  CLUSTER_KEYWORDS,
  REFERRER_PATTERNS,
} from './intent-keywords';

export type { IntentCluster, DetectionSource } from './intent-keywords';

/**
 * Detect intent cluster from a search term by matching keywords.
 * Uses NFKD normalization + combining-mark removal for accent-insensitive matching.
 *
 * Scores clusters by number of keyword matches; returns the highest-scoring
 * cluster, or 'geral' when no keywords match.
 */
export function detectIntentFromSearchTerm(term: string): IntentCluster {
  const normalized = term
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[̀-ͯ]/g, '');

  const scores: Partial<Record<IntentCluster, number>> = {};

  for (const [cluster, keywords] of Object.entries(CLUSTER_KEYWORDS)) {
    let totalWeight = 0;
    for (const kw of keywords) {
      const normalizedKw = kw
        .toLowerCase()
        .normalize('NFKD')
        .replace(/[̀-ͯ]/g, '');
      if (normalized.includes(normalizedKw)) {
        // Weight by keyword length — longer matches are more specific
        totalWeight += normalizedKw.length;
      }
    }
    if (totalWeight > 0) {
      scores[cluster as IntentCluster] = totalWeight;
    }
  }

  if (Object.keys(scores).length === 0) return 'geral';

  return Object.entries(scores).sort((a, b) => b[1] - a[1])[0][0] as IntentCluster;
}

/**
 * Check if a keyword appears as a standalone segment within a hostname/string.
 * Matches when keyword is at start, end, or surrounded by dots — prevents
 * substring false-positives (e.g. "industria" won't match "industrial").
 */
function hostnameMatches(hostname: string, keyword: string): boolean {
  const lower = hostname.toLowerCase();
  const kw = keyword.toLowerCase();
  if (lower === kw) return true;
  if (lower.startsWith(kw + '.')) return true;
  if (lower.endsWith('.' + kw)) return true;
  if (lower.includes('.' + kw + '.')) return true;
  return false;
}

/**
 * Detect intent cluster from a referrer URL by pattern matching.
 * Extracts the hostname from valid URLs first to prevent domain-spoofing bypass.
 * Falls back to raw-string matching for shorthand values (e.g. query param ref=sebrae).
 * Returns the first matching cluster, or null when no pattern matches.
 */
export function detectIntentFromReferrer(referrer: string): IntentCluster | null {
  let target = referrer;
  try {
    // Extract hostname from valid URLs for anchored domain matching
    target = new URL(referrer).hostname;
  } catch {
    // Not a valid URL — match raw string (for query param shorthand values)
  }

  for (const [cluster, patterns] of Object.entries(REFERRER_PATTERNS)) {
    for (const kw of patterns) {
      if (hostnameMatches(target, kw)) {
        return cluster as IntentCluster;
      }
    }
  }
  return null;
}

/**
 * Combined intent detection with fallback chain.
 *
 * Priority:
 * 1. Explicit searchTerm (highest confidence)
 * 2. Query params `q`, `search`, `term`, `busca`
 * 3. Referrer URL
 * 4. Query params `ref`, `referrer`, `source`
 * 5. Fallback 'geral'
 */
export function detectIntent(options: {
  searchTerm?: string;
  referrer?: string;
  queryParams?: Record<string, string>;
}): { cluster: IntentCluster; source: DetectionSource } {
  const { searchTerm, referrer, queryParams = {} } = options;

  // 1. Explicit search term (highest confidence)
  if (searchTerm && searchTerm.trim().length > 0) {
    const fromTerm = detectIntentFromSearchTerm(searchTerm);
    if (fromTerm !== 'geral') {
      return { cluster: fromTerm, source: 'search_term' };
    }
  }

  // 2. Query params that may contain search terms
  for (const key of ['q', 'search', 'term', 'busca']) {
    const value = queryParams[key];
    if (value && value.trim().length > 0) {
      const fromQuery = detectIntentFromSearchTerm(value);
      if (fromQuery !== 'geral') {
        return { cluster: fromQuery, source: 'search_term' };
      }
    }
  }

  // 3. Referrer URL
  if (referrer && referrer.trim().length > 0) {
    const fromRef = detectIntentFromReferrer(referrer);
    if (fromRef) {
      return { cluster: fromRef, source: 'referrer' };
    }
  }

  // 4. Explicit referrer info in query params
  for (const key of ['ref', 'referrer', 'source']) {
    const value = queryParams[key];
    if (value && value.trim().length > 0) {
      const fromRef = detectIntentFromReferrer(value);
      if (fromRef) {
        return { cluster: fromRef, source: 'referrer' };
      }
    }
  }

  return { cluster: 'geral', source: 'fallback' };
}

/**
 * React hook that auto-detects intent using the browser environment.
 *
 * Reads URL search params (via next/navigation) and document.referrer
 * to build the detection context. Accepts an optional explicit searchTerm
 * override.
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { cluster, source } = useIntentDetection();
 *   // Render based on cluster...
 * }
 * ```
 */
export function useIntentDetection(searchTerm?: string): {
  cluster: IntentCluster;
  source: DetectionSource;
} {
  const searchParams = useSearchParams();

  const queryParams: Record<string, string> = {};
  if (searchParams) {
    searchParams.forEach((value, key) => {
      queryParams[key] = value;
    });
  }

  const referrer = typeof document !== 'undefined' ? document.referrer : undefined;

  return detectIntent({ searchTerm, referrer, queryParams });
}
