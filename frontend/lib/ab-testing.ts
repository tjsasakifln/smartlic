/**
 * A/B Testing Infrastructure for pSEO pages.
 * CONV-012 (#1323).
 *
 * Cookie-based split + Mixpanel impression tracking.
 * All functions are SSR-safe (return early when window is unavailable).
 * All functions never throw — errors are swallowed silently.
 *
 * === Architecture ===
 *
 * The system follows a "no-invention" approach:
 * - Cookie persists 30 days for experience consistency
 * - Hash-based assignment so the same user always sees the same variant
 * - Impression tracking via existing Mixpanel setup (LGPD consent gate)
 * - SSR-safe: no window/document access during server rendering
 *
 * === Usage ===
 *
 *   // Direct API:
 *   const variant = getOrSetVariant('experiment-id', ['control', 'variant_a']);
 *   trackExperimentImpression('experiment-id', variant);
 *
 *   // React component (preferred):
 *   <AbTest
 *     experimentId="pseo-cta-v1"
 *     variants={{
 *       control: <CurrentCTASection />,
 *       variant_a: <AlternativeCTASection />,
 *     }}
 *   />
 */

import mixpanel from 'mixpanel-browser';
import { getCookieConsent } from '@/app/components/CookieConsentBanner';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COOKIE_PREFIX = 'smartlic_ab_';
const COOKIE_EXPIRY_DAYS = 30;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * A map of variant names to their rendered React nodes.
 * At least one entry is required (the control).
 */
export type VariantsMap = Record<string, React.ReactNode>;

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function isTrackingEnabled(): boolean {
  if (typeof window === 'undefined') return false;
  if (!process.env.NEXT_PUBLIC_MIXPANEL_TOKEN) return false;
  const consent = getCookieConsent();
  return consent?.analytics === true;
}

/**
 * Set a cookie with the given name, value, and expiry days.
 * Falls back to document.cookie — works in browser environments.
 */
function setCookie(name: string, value: string, days: number): void {
  try {
    const expires = new Date();
    expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
    document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)};expires=${expires.toUTCString()};path=/;SameSite=Lax`;
  } catch {
    // SSR or cookie-blocked — swallow silently
  }
}

/**
 * Read a cookie by name from document.cookie.
 * Returns null if the cookie does not exist or if not in a browser.
 */
function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  try {
    const match = document.cookie.match(
      new RegExp(`(?:^|;\\s*)${encodeURIComponent(name)}=([^;]*)`),
    );
    return match ? decodeURIComponent(match[1]) : null;
  } catch {
    return null;
  }
}

/**
 * Simple deterministic hash for variant assignment.
 * Uses a basic string hash (djb2) so the same seed always maps
 * to the same variant index.
 */
function hashString(str: string): number {
  let hash = 5381;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) + hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

/**
 * Build a deterministic seed for variant assignment.
 * Uses userId if available, otherwise a random seed stored in sessionStorage.
 * This ensures the same visitor (even anonymous) sees the same variant
 * within a session.
 */
function getOrCreateSeed(): string {
  if (typeof window === 'undefined') return 'ssr-seed';

  try {
    // Try to get a user identifier from Supabase session storage
    // Falls back to session-scoped random seed
    const STORAGE_KEY = 'smartlic_ab_seed';
    let seed = sessionStorage.getItem(STORAGE_KEY);
    if (!seed) {
      seed = `anon-${crypto.randomUUID()}`;
      sessionStorage.setItem(STORAGE_KEY, seed);
    }
    return seed;
  } catch {
    return `anon-${Math.random().toString(36).slice(2, 10)}`;
  }
}

/**
 * Build the full cookie name for an experiment.
 */
function getCookieName(experimentId: string): string {
  return `${COOKIE_PREFIX}${experimentId}`;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Get or assign a variant for the given experiment.
 *
 * - If the user already has a cookie for this experiment, returns the stored variant.
 * - If not, assigns a deterministic variant based on a seed (userId or random).
 * - Stores the assignment in a cookie with 30-day expiry.
 * - SSR-safe: returns the first variant on the server.
 *
 * @param experimentId - Unique identifier for the experiment (e.g. "pseo-cta-v1").
 * @param variants - Array of variant names (e.g. ["control", "variant_a"]).
 *                   The first variant is the default/control.
 * @returns The assigned variant name.
 */
export function getOrSetVariant(
  experimentId: string,
  variants: string[],
): string {
  // Validate input
  if (!experimentId || !variants || variants.length === 0) {
    return 'control';
  }

  // SSR: return first variant (control) — no cookies on server
  if (typeof window === 'undefined') {
    return variants[0];
  }

  const cookieName = getCookieName(experimentId);

  // Check existing cookie
  const existing = getCookie(cookieName);
  if (existing && variants.includes(existing)) {
    return existing;
  }

  // Assign new variant deterministically
  const seed = getOrCreateSeed();
  const hash = hashString(`${experimentId}:${seed}`);
  const index = hash % variants.length;
  const variant = variants[index];

  // Persist in cookie
  setCookie(cookieName, variant, COOKIE_EXPIRY_DAYS);

  return variant;
}

/**
 * Track an experiment impression in Mixpanel.
 * Event name: "Experiment Impression"
 * Properties: experiment_id, variant, page_path
 *
 * Respects LGPD cookie consent. SSR-safe. Never throws.
 *
 * @param experimentId - The experiment identifier.
 * @param variant - The assigned variant name.
 */
export function trackExperimentImpression(
  experimentId: string,
  variant: string,
): void {
  if (!isTrackingEnabled()) return;

  try {
    const pagePath =
      typeof window !== 'undefined' ? window.location.pathname : '';

    mixpanel.track('Experiment Impression', {
      experiment_id: experimentId,
      variant,
      page_path: pagePath,
      timestamp: new Date().toISOString(),
      environment: process.env.NODE_ENV || 'development',
    });
  } catch {
    // Mixpanel not initialized or error — swallow silently
  }
}

/**
 * Get all active experiment cookies from the current page.
 * Useful for analytics and debugging.
 *
 * @returns A record of experiment IDs to their assigned variants.
 */
export function getActiveExperiments(): Record<string, string> {
  if (typeof document === 'undefined') return {};

  try {
    const experiments: Record<string, string> = {};
    const cookies = document.cookie.split(';').map((c) => c.trim());

    for (const cookie of cookies) {
      const eqPos = cookie.indexOf('=');
      if (eqPos === -1) continue;
      const name = decodeURIComponent(cookie.slice(0, eqPos));
      const value = decodeURIComponent(cookie.slice(eqPos + 1));

      if (name.startsWith(COOKIE_PREFIX)) {
        const experimentId = name.slice(COOKIE_PREFIX.length);
        experiments[experimentId] = value;
      }
    }

    return experiments;
  } catch {
    return {};
  }
}
