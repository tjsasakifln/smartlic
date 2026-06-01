/**
 * Tests for conversion analytics event tracker (lib/analytics/conversion-tracker.ts).
 * CONV-009 (#1318)
 *
 * Verifies:
 * - LGPD consent gate blocks/allows tracking
 * - SSR-safe: no call when window is undefined
 * - Mixpanel token missing blocks tracking
 * - Each layer event forwards correct event name and props
 * - Errors from mixpanel.track are swallowed (never throws)
 * - Timestamp and environment are included in every event
 */

import mixpanel from 'mixpanel-browser';

jest.mock('mixpanel-browser', () => ({
  __esModule: true,
  default: { track: jest.fn() },
}));

jest.mock('@/app/components/CookieConsentBanner', () => ({
  getCookieConsent: jest.fn(),
}));

import { getCookieConsent } from '@/app/components/CookieConsentBanner';
import {
  trackPageScroll,
  trackInsightCardView,
  trackInsightCardClick,
  trackInternalSearchQuery,
  trackInternalSearchResultClick,
  trackTimeOnPage,
  trackCTAView,
  trackCTAClick,
  trackPreviewUnlockAttempt,
  trackWhatsAppClick,
  trackDemoRequestStart,
  trackDemoRequestSubmit,
  trackSignupStart,
  trackSignupComplete,
  trackSignupError,
  trackCheckoutStart,
  trackCheckoutComplete,
  trackCheckoutAbandoned,
  trackReportPreviewView,
  trackReportPurchaseStart,
  trackReportPurchaseComplete,
  trackAlertSubscriptionStart,
  trackAlertSubscriptionComplete,
  trackRevenueEvent,
} from '../conversion-tracker';

const mockTrack = mixpanel.track as jest.Mock;
const mockGetConsent = getCookieConsent as jest.Mock;

beforeEach(() => {
  mockTrack.mockClear();
  mockGetConsent.mockClear();
  // Default: consent granted
  mockGetConsent.mockReturnValue({ analytics: true });
  process.env.NEXT_PUBLIC_MIXPANEL_TOKEN = 'test-token';
});

// =========================================================================
// LGPD consent gate (tested on one representative function per layer)
// =========================================================================

describe('LGPD consent gate', () => {
  it('tracks when consent.analytics is true', () => {
    mockGetConsent.mockReturnValue({ analytics: true });
    trackPageScroll({ depth: 50 });
    expect(mockTrack).toHaveBeenCalledTimes(1);
  });

  it('does NOT track when consent.analytics is false', () => {
    mockGetConsent.mockReturnValue({ analytics: false });
    trackPageScroll({ depth: 50 });
    expect(mockTrack).not.toHaveBeenCalled();
  });

  it('does NOT track when getCookieConsent returns null', () => {
    mockGetConsent.mockReturnValue(null);
    trackCTAView({ cta_id: 'hero', cta_position: 'hero' });
    expect(mockTrack).not.toHaveBeenCalled();
  });

  it('does NOT track when NEXT_PUBLIC_MIXPANEL_TOKEN is missing', () => {
    delete process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;
    trackCheckoutStart({ plan: 'mensal', amount_cents: 4990 });
    expect(mockTrack).not.toHaveBeenCalled();
  });
});

// =========================================================================
// SSR safety
// =========================================================================

describe('SSR safety', () => {
  it('does NOT track when window is undefined', () => {
    const originalWindow = global.window;
    // @ts-expect-error intentional SSR simulation
    delete global.window;
    trackSignupComplete({ method: 'email' });
    expect(mockTrack).not.toHaveBeenCalled();
    global.window = originalWindow;
  });
});

// =========================================================================
// Error swallowing
// =========================================================================

describe('error swallowing', () => {
  it('does not throw when mixpanel.track throws', () => {
    mockTrack.mockImplementationOnce(() => {
      throw new Error('Mixpanel not initialized');
    });
    expect(() => trackRevenueEvent({
      revenue_type: 'subscription_new',
      amount_cents: 4990,
    })).not.toThrow();
  });

  it('does not throw when mixpanel.track throws a non-Error value', () => {
    mockTrack.mockImplementationOnce(() => {
      // eslint-disable-next-line @typescript-eslint/no-throw-literal
      throw 'not-initialized';
    });
    expect(() => trackSignupError({ error: 'validation' })).not.toThrow();
  });
});

// =========================================================================
// Layer 1 — Engagement event forwarding
// =========================================================================

describe('Layer 1 — Engagement events', () => {
  it('trackPageScroll fires page_scroll_25', () => {
    trackPageScroll({ depth: 25, page_height: 2000, viewport_height: 800 });
    expect(mockTrack).toHaveBeenCalledWith(
      'page_scroll_25',
      expect.objectContaining({ depth: 25, page_height: 2000, viewport_height: 800 }),
    );
  });

  it('trackPageScroll fires page_scroll_100', () => {
    trackPageScroll({ depth: 100, source_template: 'fornecedor_page', entity_id: '123' });
    expect(mockTrack).toHaveBeenCalledWith(
      'page_scroll_100',
      expect.objectContaining({ depth: 100, source_template: 'fornecedor_page', entity_id: '123' }),
    );
  });

  it('trackInsightCardView fires insight_card_view', () => {
    trackInsightCardView({ card_id: 'card-0', card_type: 'viability', entity_id: '123' });
    expect(mockTrack).toHaveBeenCalledWith(
      'insight_card_view',
      expect.objectContaining({ card_id: 'card-0', card_type: 'viability' }),
    );
  });

  it('trackInsightCardClick fires insight_card_click', () => {
    trackInsightCardClick({ card_id: 'card-1', card_type: 'summary' });
    expect(mockTrack).toHaveBeenCalledWith(
      'insight_card_click',
      expect.objectContaining({ card_id: 'card-1' }),
    );
  });

  it('trackInternalSearchQuery fires internal_search_query', () => {
    trackInternalSearchQuery({ query: 'pavimentacao', result_count: 5 });
    expect(mockTrack).toHaveBeenCalledWith(
      'internal_search_query',
      expect.objectContaining({ query: 'pavimentacao', result_count: 5 }),
    );
  });

  it('trackInternalSearchResultClick fires internal_search_result_click', () => {
    trackInternalSearchResultClick({ query: 'asfalto', result_index: 2, result_id: 'bid-123' });
    expect(mockTrack).toHaveBeenCalledWith(
      'internal_search_result_click',
      expect.objectContaining({ query: 'asfalto', result_index: 2 }),
    );
  });

  it('trackTimeOnPage fires time_on_page_30s', () => {
    trackTimeOnPage({ seconds: 30 });
    expect(mockTrack).toHaveBeenCalledWith(
      'time_on_page_30s',
      expect.objectContaining({ seconds: 30 }),
    );
  });

  it('trackTimeOnPage fires time_on_page_120s', () => {
    trackTimeOnPage({ seconds: 120 });
    expect(mockTrack).toHaveBeenCalledWith(
      'time_on_page_120s',
      expect.objectContaining({ seconds: 120 }),
    );
  });
});

// =========================================================================
// Layer 2 — Intent event forwarding
// =========================================================================

describe('Layer 2 — Intent events', () => {
  it('trackCTAView fires cta_view', () => {
    trackCTAView({ cta_id: 'hero-cta', cta_position: 'hero', cta_variant: 'primary', source_template: 'fornecedor_page' });
    expect(mockTrack).toHaveBeenCalledWith(
      'cta_view',
      expect.objectContaining({ cta_id: 'hero-cta', cta_position: 'hero', cta_variant: 'primary' }),
    );
  });

  it('trackCTAClick fires cta_click', () => {
    trackCTAClick({ cta_id: 'sticky-trial', cta_position: 'sticky', cta_destination: '/signup' });
    expect(mockTrack).toHaveBeenCalledWith(
      'cta_click',
      expect.objectContaining({ cta_id: 'sticky-trial', cta_destination: '/signup' }),
    );
  });

  it('trackPreviewUnlockAttempt fires preview_unlock_attempt', () => {
    trackPreviewUnlockAttempt({ gate_type: 'free_trial', preview_id: 'edital_list', unlocked: true });
    expect(mockTrack).toHaveBeenCalledWith(
      'preview_unlock_attempt',
      expect.objectContaining({ gate_type: 'free_trial', preview_id: 'edital_list', unlocked: true }),
    );
  });

  it('trackWhatsAppClick fires whatsapp_click', () => {
    trackWhatsAppClick({ origin: 'footer', number: '5511999999999' });
    expect(mockTrack).toHaveBeenCalledWith(
      'whatsapp_click',
      expect.objectContaining({ origin: 'footer', number: '5511999999999' }),
    );
  });

  it('trackDemoRequestStart fires demo_request_start', () => {
    trackDemoRequestStart({ company_name: 'Teste Ltda', source_template: 'landing' });
    expect(mockTrack).toHaveBeenCalledWith(
      'demo_request_start',
      expect.objectContaining({ company_name: 'Teste Ltda' }),
    );
  });

  it('trackDemoRequestSubmit fires demo_request_submit', () => {
    trackDemoRequestSubmit({ email: 'teste@teste.com', source_template: 'landing' });
    expect(mockTrack).toHaveBeenCalledWith(
      'demo_request_submit',
      expect.objectContaining({ email: 'teste@teste.com' }),
    );
  });
});

// =========================================================================
// Layer 3 — Conversion event forwarding
// =========================================================================

describe('Layer 3 — Conversion events', () => {
  it('trackSignupStart fires signup_start', () => {
    trackSignupStart({ method: 'google', utm_source: 'google', utm_campaign: 'pseo' });
    expect(mockTrack).toHaveBeenCalledWith(
      'signup_start',
      expect.objectContaining({ method: 'google', utm_source: 'google' }),
    );
  });

  it('trackSignupComplete fires signup_complete', () => {
    trackSignupComplete({ method: 'email' });
    expect(mockTrack).toHaveBeenCalledWith(
      'signup_complete',
      expect.objectContaining({ method: 'email' }),
    );
  });

  it('trackSignupError fires signup_error', () => {
    trackSignupError({ method: 'email', error: 'email_already_exists' });
    expect(mockTrack).toHaveBeenCalledWith(
      'signup_error',
      expect.objectContaining({ error: 'email_already_exists' }),
    );
  });

  it('trackCheckoutStart fires checkout_start', () => {
    trackCheckoutStart({ plan: 'mensal', amount_cents: 4990, interval: 'month' });
    expect(mockTrack).toHaveBeenCalledWith(
      'checkout_start',
      expect.objectContaining({ plan: 'mensal', amount_cents: 4990, interval: 'month' }),
    );
  });

  it('trackCheckoutComplete fires checkout_complete', () => {
    trackCheckoutComplete({ plan: 'anual', amount_cents: 39990, interval: 'year' });
    expect(mockTrack).toHaveBeenCalledWith(
      'checkout_complete',
      expect.objectContaining({ plan: 'anual', amount_cents: 39990 }),
    );
  });

  it('trackCheckoutAbandoned fires checkout_abandoned', () => {
    trackCheckoutAbandoned({ plan: 'mensal', abandon_reason: 'price_too_high' });
    expect(mockTrack).toHaveBeenCalledWith(
      'checkout_abandoned',
      expect.objectContaining({ plan: 'mensal', abandon_reason: 'price_too_high' }),
    );
  });

  it('trackReportPreviewView fires report_preview_view', () => {
    trackReportPreviewView({ report_type: 'intel_report', session_id: 'sess-123' });
    expect(mockTrack).toHaveBeenCalledWith(
      'report_preview_view',
      expect.objectContaining({ report_type: 'intel_report', session_id: 'sess-123' }),
    );
  });

  it('trackReportPurchaseStart fires report_purchase_start', () => {
    trackReportPurchaseStart({ report_type: 'viability_report', amount_cents: 1990 });
    expect(mockTrack).toHaveBeenCalledWith(
      'report_purchase_start',
      expect.objectContaining({ report_type: 'viability_report', amount_cents: 1990 }),
    );
  });

  it('trackReportPurchaseComplete fires report_purchase_complete', () => {
    trackReportPurchaseComplete({ report_type: 'intel_report', amount_cents: 4990, session_id: 'sess-456' });
    expect(mockTrack).toHaveBeenCalledWith(
      'report_purchase_complete',
      expect.objectContaining({ report_type: 'intel_report', amount_cents: 4990 }),
    );
  });

  it('trackAlertSubscriptionStart fires alert_subscription_start', () => {
    trackAlertSubscriptionStart({ alert_type: 'setor', alert_target: 'informatica' });
    expect(mockTrack).toHaveBeenCalledWith(
      'alert_subscription_start',
      expect.objectContaining({ alert_type: 'setor', alert_target: 'informatica' }),
    );
  });

  it('trackAlertSubscriptionComplete fires alert_subscription_complete', () => {
    trackAlertSubscriptionComplete({ alert_type: 'fornecedor', alert_target: '12345678000100' });
    expect(mockTrack).toHaveBeenCalledWith(
      'alert_subscription_complete',
      expect.objectContaining({ alert_type: 'fornecedor' }),
    );
  });
});

// =========================================================================
// Layer 4 — Revenue event forwarding
// =========================================================================

describe('Layer 4 — Revenue events', () => {
  it('trackRevenueEvent fires revenue_event with subscription_new', () => {
    trackRevenueEvent({
      revenue_type: 'subscription_new',
      amount_cents: 4990,
      product: 'smartlic-mensal',
      template: 'fornecedor_page',
      intent_cluster: 'fornecedor',
      query_origin: 'fornecedor de asfalto sc',
      utm_source: 'google',
    });
    expect(mockTrack).toHaveBeenCalledWith(
      'revenue_event',
      expect.objectContaining({
        revenue_type: 'subscription_new',
        amount_cents: 4990,
        currency: 'BRL',
        product: 'smartlic-mensal',
        template: 'fornecedor_page',
        intent_cluster: 'fornecedor',
        query_origin: 'fornecedor de asfalto sc',
        utm_source: 'google',
      }),
    );
  });

  it('trackRevenueEvent defaults currency to BRL', () => {
    trackRevenueEvent({
      revenue_type: 'microtransaction',
      amount_cents: 990,
    });
    expect(mockTrack).toHaveBeenCalledWith(
      'revenue_event',
      expect.objectContaining({ currency: 'BRL' }),
    );
  });

  it('trackRevenueEvent allows custom currency', () => {
    trackRevenueEvent({
      revenue_type: 'subscription_renewal',
      amount_cents: 5000,
      currency: 'USD',
    });
    expect(mockTrack).toHaveBeenCalledWith(
      'revenue_event',
      expect.objectContaining({ currency: 'USD' }),
    );
  });

  it('trackRevenueEvent includes transaction_id when provided', () => {
    trackRevenueEvent({
      revenue_type: 'subscription_new',
      amount_cents: 4990,
      transaction_id: 'txn-abc-123',
    });
    expect(mockTrack).toHaveBeenCalledWith(
      'revenue_event',
      expect.objectContaining({ transaction_id: 'txn-abc-123' }),
    );
  });
});

// =========================================================================
// Timestamp and environment in every event
// =========================================================================

describe('metadata in every event', () => {
  it('includes timestamp and environment in all events', () => {
    trackPageScroll({ depth: 50 });
    const callArgs = mockTrack.mock.calls[0][1];
    expect(callArgs).toHaveProperty('timestamp');
    expect(callArgs).toHaveProperty('environment');
  });
});
