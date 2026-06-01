/**
 * Tests for pSEO analytics wrappers (lib/analytics/pseo.ts).
 * PSEO-CONV-001 (#884)
 *
 * Verifies:
 * - LGPD consent gate blocks tracking when consent is absent
 * - LGPD consent gate allows tracking when consent is given
 * - SSR-safe: no call when window is undefined
 * - Mixpanel token missing blocks tracking
 * - Each event call passes event name and props through
 * - Errors from mixpanel.track are swallowed (never throws)
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
import { trackPseoEvent } from '../pseo';

const mockTrack = mixpanel.track as jest.Mock;
const mockGetConsent = getCookieConsent as jest.Mock;

const VALID_PROPS = {
  source_template: 'fornecedor_page' as const,
  page_url: 'https://smartlic.tech/fornecedores/12345678000100',
};

beforeEach(() => {
  mockTrack.mockClear();
  mockGetConsent.mockClear();
  // Default: consent granted
  mockGetConsent.mockReturnValue({ analytics: true });
  process.env.NEXT_PUBLIC_MIXPANEL_TOKEN = 'test-token';
  // window is defined in Jest jsdom environment
});

// ---------------------------------------------------------------------------
// LGPD consent gate
// ---------------------------------------------------------------------------

describe('LGPD consent gate', () => {
  it('tracks when consent.analytics is true', () => {
    mockGetConsent.mockReturnValue({ analytics: true });
    trackPseoEvent('pseo_supplier_viewed', VALID_PROPS);
    expect(mockTrack).toHaveBeenCalledTimes(1);
  });

  it('does NOT track when consent.analytics is false', () => {
    mockGetConsent.mockReturnValue({ analytics: false });
    trackPseoEvent('pseo_supplier_viewed', VALID_PROPS);
    expect(mockTrack).not.toHaveBeenCalled();
  });

  it('does NOT track when getCookieConsent returns null', () => {
    mockGetConsent.mockReturnValue(null);
    trackPseoEvent('pseo_supplier_viewed', VALID_PROPS);
    expect(mockTrack).not.toHaveBeenCalled();
  });

  it('does NOT track when NEXT_PUBLIC_MIXPANEL_TOKEN is missing', () => {
    delete process.env.NEXT_PUBLIC_MIXPANEL_TOKEN;
    mockGetConsent.mockReturnValue({ analytics: true });
    trackPseoEvent('pseo_supplier_viewed', VALID_PROPS);
    expect(mockTrack).not.toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// SSR-safe
// ---------------------------------------------------------------------------

describe('SSR safety', () => {
  it('does NOT track when window is undefined', () => {
    const originalWindow = global.window;
    // @ts-expect-error intentional SSR simulation
    delete global.window;
    trackPseoEvent('pseo_supplier_viewed', VALID_PROPS);
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
    expect(() => trackPseoEvent('pseo_supplier_viewed', VALID_PROPS)).not.toThrow();
  });

  it('does not throw when mixpanel.track throws a non-Error value', () => {
    mockTrack.mockImplementationOnce(() => {
      // eslint-disable-next-line @typescript-eslint/no-throw-literal
      throw 'not-initialized';
    });
    expect(() => trackPseoEvent('pseo_checkout_click', VALID_PROPS)).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Event forwarding
// ---------------------------------------------------------------------------

describe('event forwarding', () => {
  it('forwards pseo_supplier_viewed with source_template and page_url', () => {
    const props = { source_template: 'fornecedor_page' as const, page_url: 'https://smartlic.tech/fornecedores/123', cnpj: '12345678000100' };
    trackPseoEvent('pseo_supplier_viewed', props);
    expect(mockTrack).toHaveBeenCalledWith(
      'pseo_supplier_viewed',
      expect.objectContaining({ source_template: 'fornecedor_page', cnpj: '12345678000100' }),
    );
  });

  it('forwards pseo_organ_viewed', () => {
    const props = { source_template: 'orgao_page' as const, orgao_cnpj: '99887766000100' };
    trackPseoEvent('pseo_organ_viewed', props);
    expect(mockTrack).toHaveBeenCalledWith(
      'pseo_organ_viewed',
      expect.objectContaining({ source_template: 'orgao_page' }),
    );
  });

  it('forwards pseo_alert_signup with tipo', () => {
    const props = { source_template: 'fornecedor_page' as const, tipo: 'fornecedor', cnpj: '12345678000100' };
    trackPseoEvent('pseo_alert_signup', props);
    expect(mockTrack).toHaveBeenCalledWith(
      'pseo_alert_signup',
      expect.objectContaining({ tipo: 'fornecedor' }),
    );
  });

  it('forwards pseo_calculator_result with indice and periodicidade', () => {
    const props = { source_template: 'calculadora_reajuste' as const, indice: 'IPCA', periodicidade: 'anual', periodos: 2 };
    trackPseoEvent('pseo_calculator_result', props);
    expect(mockTrack).toHaveBeenCalledWith(
      'pseo_calculator_result',
      expect.objectContaining({ indice: 'IPCA', periodicidade: 'anual' }),
    );
  });

  it('forwards pseo_checkout_click with destination', () => {
    const props = { source_template: 'fornecedor_page' as const, destination: '/signup?ref=cnpj&cnpj=123&utm_source=pseo' };
    trackPseoEvent('pseo_checkout_click', props);
    expect(mockTrack).toHaveBeenCalledWith(
      'pseo_checkout_click',
      expect.objectContaining({ destination: '/signup?ref=cnpj&cnpj=123&utm_source=pseo' }),
    );
  });

  it('forwards pseo_edital_viewed with edital_id', () => {
    const props = { source_template: 'blog_hub' as const, edital_id: 'pncp-abc-123' };
    trackPseoEvent('pseo_edital_viewed', props);
    expect(mockTrack).toHaveBeenCalledWith(
      'pseo_edital_viewed',
      expect.objectContaining({ edital_id: 'pncp-abc-123' }),
    );
  });

  it('forwards pseo_contrato_viewed with source_template and entity_id', () => {
    const props = { source_template: 'contrato_page' as const, entity_id: 'pncp-contrato-456', setor: 'pavimentacao-asfaltica', uf: 'SC' };
    trackPseoEvent('pseo_contrato_viewed', props);
    expect(mockTrack).toHaveBeenCalledWith(
      'pseo_contrato_viewed',
      expect.objectContaining({ source_template: 'contrato_page', entity_id: 'pncp-contrato-456', setor: 'pavimentacao-asfaltica', uf: 'SC' }),
    );
  });

  it('includes timestamp and environment in every tracked event', () => {
    trackPseoEvent('pseo_lead_captured', { source_template: 'orgao_page' as const });
    const callArgs = mockTrack.mock.calls[0][1];
    expect(callArgs).toHaveProperty('timestamp');
    expect(callArgs).toHaveProperty('environment');
  });
});
