/**
 * Tests for A/B testing library (lib/ab-testing.ts).
 * CONV-012 (#1323).
 *
 * Verifies:
 * - getOrSetVariant cookie persistence and consistency
 * - getOrSetVariant hash-based assignment (deterministic)
 * - getOrSetVariant SSR-safe (window undefined)
 * - getOrSetVariant respects existing cookies
 * - trackExperimentImpression sends correct Mixpanel event
 * - trackExperimentImpression respects LGPD consent gate
 * - trackExperimentImpression SSR-safe
 * - getActiveExperiments returns active experiments
 */

import mixpanel from 'mixpanel-browser';

// Mock mixpanel-browser
jest.mock('mixpanel-browser', () => ({
  __esModule: true,
  default: { track: jest.fn() },
}));

// Mock CookieConsentBanner
jest.mock('@/app/components/CookieConsentBanner', () => ({
  getCookieConsent: jest.fn(),
}));

import { getCookieConsent } from '@/app/components/CookieConsentBanner';
import {
  getOrSetVariant,
  trackExperimentImpression,
  getActiveExperiments,
} from '../ab-testing';

const mockTrack = mixpanel.track as jest.Mock;
const mockGetConsent = getCookieConsent as jest.Mock;

// Cookie test helpers
function setDocumentCookie(name: string, value: string): void {
  document.cookie = `${encodeURIComponent(name)}=${encodeURIComponent(value)};path=/`;
}

function clearAllCookies(): void {
  document.cookie.split(';').forEach((c) => {
    const eqPos = c.indexOf('=');
    const name = eqPos > -1 ? c.slice(0, eqPos).trim() : c.trim();
    document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 GMT;path=/`;
  });
}

beforeEach(() => {
  mockTrack.mockClear();
  mockGetConsent.mockClear();
  // Default: consent granted
  mockGetConsent.mockReturnValue({ analytics: true });
  process.env.NEXT_PUBLIC_MIXPANEL_TOKEN = 'test-token';
  clearAllCookies();
});

afterAll(() => {
  delete process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;
});

// ---------------------------------------------------------------------------
// getOrSetVariant
// ---------------------------------------------------------------------------

describe('getOrSetVariant', () => {
  it('returns the first variant when called on SSR (window undefined)', () => {
    const originalWindow = global.window;
    // @ts-expect-error intentional SSR simulation
    delete global.window;

    const result = getOrSetVariant('test-exp', ['control', 'variant_a']);

    expect(result).toBe('control');
    global.window = originalWindow;
  });

  it('returns "control" for invalid inputs', () => {
    // @ts-expect-error testing invalid input
    expect(getOrSetVariant('', ['control'])).toBe('control');
    // @ts-expect-error testing invalid input
    expect(getOrSetVariant('test-exp', [])).toBe('control');
    // @ts-expect-error testing invalid input
    expect(getOrSetVariant('test-exp', null)).toBe('control');
  });

  it('stores the assigned variant in a cookie', () => {
    const variant = getOrSetVariant('test-exp', ['control', 'variant_a']);

    // Cookie should exist
    const cookieName = 'smartlic_ab_test-exp';
    expect(document.cookie).toContain(encodeURIComponent(cookieName));
    expect(document.cookie).toContain(encodeURIComponent(variant));
  });

  it('returns the same variant on repeated calls (cookie persistence)', () => {
    const firstCall = getOrSetVariant('test-persist', ['control', 'variant_a', 'variant_b']);
    const secondCall = getOrSetVariant('test-persist', ['control', 'variant_a', 'variant_b']);
    const thirdCall = getOrSetVariant('test-persist', ['control', 'variant_a', 'variant_b']);

    // All calls should return the same variant
    expect(firstCall).toBe(secondCall);
    expect(secondCall).toBe(thirdCall);
  });

  it('respects an existing cookie value', () => {
    const cookieName = 'smartlic_ab_respect-cookie';
    setDocumentCookie(cookieName, 'variant_b');

    const result = getOrSetVariant('respect-cookie', ['control', 'variant_a', 'variant_b']);
    expect(result).toBe('variant_b');
  });

  it('returns a valid variant from the provided list', () => {
    const variants = ['control', 'variant_a', 'variant_b'];
    const result = getOrSetVariant('validity-check', variants);
    expect(variants).toContain(result);
  });

  it('handles a single variant (no split)', () => {
    const result = getOrSetVariant('single-variant', ['control']);
    expect(result).toBe('control');
  });
});

// ---------------------------------------------------------------------------
// Deterministic assignment
// ---------------------------------------------------------------------------

describe('deterministic assignment', () => {
  it('assigns the same variant consistently (cookie persistence)', () => {
    // First call assigns and stores variant in cookie
    const first = getOrSetVariant('det-exp', ['control', 'variant_a']);

    // Subsequent calls should read the cookie and return the same variant
    for (let i = 0; i < 10; i++) {
      expect(getOrSetVariant('det-exp', ['control', 'variant_a'])).toBe(first);
    }
  });

  it('can distribute across multiple variants with different seeds', () => {
    // This test verifies that hash function distributes
    // Different experiment IDs produce different variant assignments
    const results = new Set<string>();
    for (let i = 0; i < 10; i++) {
      clearAllCookies();
      sessionStorage.removeItem('smartlic_ab_seed');
      const variant = getOrSetVariant(`multi-exp-${i}`, ['control', 'variant_a']);
      results.add(variant);
    }

    // Both control and variant_a should appear
    expect(results).toContain('control');
    expect(results).toContain('variant_a');
  });
});

// ---------------------------------------------------------------------------
// trackExperimentImpression
// ---------------------------------------------------------------------------

describe('trackExperimentImpression', () => {
  it('sends "Experiment Impression" event with correct properties', () => {
    trackExperimentImpression('test-exp', 'variant_a');

    expect(mockTrack).toHaveBeenCalledWith(
      'Experiment Impression',
      expect.objectContaining({
        experiment_id: 'test-exp',
        variant: 'variant_a',
      }),
    );
  });

  it('includes page_path in the event properties', () => {
    trackExperimentImpression('test-exp-2', 'control');

    expect(mockTrack).toHaveBeenCalledWith(
      'Experiment Impression',
      expect.objectContaining({
        page_path: expect.any(String),
      }),
    );
  });

  it('includes timestamp and environment in every event', () => {
    trackExperimentImpression('test-exp', 'control');

    const callArgs = mockTrack.mock.calls[0][1];
    expect(callArgs).toHaveProperty('timestamp');
    expect(callArgs).toHaveProperty('environment');
  });

  it('does NOT track when consent.analytics is false', () => {
    mockGetConsent.mockReturnValue({ analytics: false });

    trackExperimentImpression('test-exp', 'control');
    expect(mockTrack).not.toHaveBeenCalled();
  });

  it('does NOT track when getCookieConsent returns null', () => {
    mockGetConsent.mockReturnValue(null);

    trackExperimentImpression('test-exp', 'control');
    expect(mockTrack).not.toHaveBeenCalled();
  });

  it('does NOT track when NEXT_PUBLIC_MIXPANEL_TOKEN is missing', () => {
    delete process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;

    trackExperimentImpression('test-exp', 'control');
    expect(mockTrack).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// SSR safety
// ---------------------------------------------------------------------------

describe('SSR safety', () => {
  it('does NOT track Experiment Impression when window is undefined', () => {
    const originalWindow = global.window;
    // @ts-expect-error intentional SSR simulation
    delete global.window;

    trackExperimentImpression('test-exp', 'control');
    expect(mockTrack).not.toHaveBeenCalled();
    global.window = originalWindow;
  });
});

// ---------------------------------------------------------------------------
// Error swallowing
// ---------------------------------------------------------------------------

describe('error swallowing', () => {
  it('does not throw when mixpanel.track throws', () => {
    mockTrack.mockImplementationOnce(() => {
      throw new Error('Mixpanel not initialized');
    });

    expect(() =>
      trackExperimentImpression('test-exp', 'control'),
    ).not.toThrow();
  });

  it('does not throw when mixpanel.track throws a non-Error value', () => {
    mockTrack.mockImplementationOnce(() => {
      // eslint-disable-next-line @typescript-eslint/no-throw-literal
      throw 'not-initialized';
    });

    expect(() =>
      trackExperimentImpression('test-exp', 'control'),
    ).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// getActiveExperiments
// ---------------------------------------------------------------------------

describe('getActiveExperiments', () => {
  it('returns an empty object when no AB cookies exist', () => {
    const experiments = getActiveExperiments();
    expect(experiments).toEqual({});
  });

  it('returns active AB experiments with their variants', () => {
    setDocumentCookie('smartlic_ab_exp1', 'control');
    setDocumentCookie('smartlic_ab_exp2', 'variant_a');
    setDocumentCookie('some_other_cookie', 'value');

    const experiments = getActiveExperiments();
    expect(experiments).toEqual({
      exp1: 'control',
      exp2: 'variant_a',
    });
  });

  it('does not include non-AB cookies', () => {
    setDocumentCookie('smartlic_ab_exp1', 'control');
    setDocumentCookie('session_id', 'abc123');

    const experiments = getActiveExperiments();
    expect(experiments).toEqual({ exp1: 'control' });
  });
});
