/**
 * Tests for founders analytics wrappers (lib/analytics/founders.ts).
 *
 * Verifies:
 * - safeTrack swallows errors from Mixpanel (never throws)
 * - Each exported event wrapper calls mixpanel.track with the correct event
 *   name and forwards props unchanged
 */

import mixpanel from 'mixpanel-browser';

jest.mock('mixpanel-browser', () => ({
  __esModule: true,
  default: { track: jest.fn() },
}));

import {
  trackFoundersPageView,
  trackFoundersBannerView,
  trackFoundersBannerClick,
  trackFoundersBannerDismiss,
  trackFoundersRibbonView,
  trackFoundersRibbonClick,
  trackFoundersCtaClick,
  trackFoundersCheckoutStart,
  trackFoundersPseoConversion,
  trackFoundersCheckoutAbandoned,
  trackFoundersCheckoutError,
  trackFoundersInviteSent,
  trackFoundersAccountActivated,
  trackFoundersCountdownViewed,
} from '../founders';

const mockTrack = mixpanel.track as jest.Mock;

beforeEach(() => {
  mockTrack.mockClear();
});

// ---------------------------------------------------------------------------
// safeTrack — error swallowing
// ---------------------------------------------------------------------------

describe('safeTrack error swallowing', () => {
  it('does not throw when mixpanel.track throws', () => {
    mockTrack.mockImplementationOnce(() => {
      throw new Error('Mixpanel not initialized');
    });

    expect(() =>
      trackFoundersPageView({ utm_source: null, utm_medium: null, utm_campaign: null })
    ).not.toThrow();
  });

  it('does not throw when mixpanel.track throws a non-Error value', () => {
    mockTrack.mockImplementationOnce(() => {
      // eslint-disable-next-line @typescript-eslint/no-throw-literal
      throw 'consent not given';
    });

    expect(() => trackFoundersCtaClick({ cta_location: 'hero' })).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Individual event wrappers
// ---------------------------------------------------------------------------

describe('trackFoundersPageView', () => {
  it('calls mixpanel.track with founders_page_view and forwarded props', () => {
    const props = {
      utm_source: 'google',
      utm_medium: 'cpc',
      utm_campaign: 'founders-2026',
      src: 'banner',
      seats_remaining: 10,
      deadline_at: '2026-05-30T23:59:59-03:00',
    };
    trackFoundersPageView(props);
    expect(mockTrack).toHaveBeenCalledWith('founders_page_view', props);
  });

  it('accepts nullish optional props', () => {
    trackFoundersPageView({ utm_source: null, utm_medium: null, utm_campaign: null });
    expect(mockTrack).toHaveBeenCalledWith('founders_page_view', {
      utm_source: null,
      utm_medium: null,
      utm_campaign: null,
    });
  });
});

describe('trackFoundersBannerView', () => {
  it('calls mixpanel.track with founders_banner_view', () => {
    trackFoundersBannerView({ route: '/buscar', dismissed_count: 2 });
    expect(mockTrack).toHaveBeenCalledWith('founders_banner_view', {
      route: '/buscar',
      dismissed_count: 2,
    });
  });
});

describe('trackFoundersBannerClick', () => {
  it('calls mixpanel.track with founders_banner_click', () => {
    trackFoundersBannerClick({ route: '/planos' });
    expect(mockTrack).toHaveBeenCalledWith('founders_banner_click', { route: '/planos' });
  });
});

describe('trackFoundersBannerDismiss', () => {
  it('calls mixpanel.track with founders_banner_dismiss', () => {
    trackFoundersBannerDismiss({ route: '/dashboard' });
    expect(mockTrack).toHaveBeenCalledWith('founders_banner_dismiss', { route: '/dashboard' });
  });
});

describe('trackFoundersRibbonView', () => {
  it('calls mixpanel.track with founders_ribbon_view and variant', () => {
    trackFoundersRibbonView({ route: '/licitacoes/tecnologia', variant: 'compact' });
    expect(mockTrack).toHaveBeenCalledWith('founders_ribbon_view', {
      route: '/licitacoes/tecnologia',
      variant: 'compact',
    });
  });
});

describe('trackFoundersRibbonClick', () => {
  it('calls mixpanel.track with founders_ribbon_click and variant', () => {
    trackFoundersRibbonClick({ route: '/observatorio/setor-ti', variant: 'default' });
    expect(mockTrack).toHaveBeenCalledWith('founders_ribbon_click', {
      route: '/observatorio/setor-ti',
      variant: 'default',
    });
  });
});

describe('trackFoundersCtaClick', () => {
  it('calls mixpanel.track with founders_cta_click and cta_location', () => {
    trackFoundersCtaClick({ cta_location: 'pricing_table', src: 'email' });
    expect(mockTrack).toHaveBeenCalledWith('founders_cta_click', {
      cta_location: 'pricing_table',
      src: 'email',
    });
  });
});

describe('trackFoundersCheckoutStart', () => {
  it('calls mixpanel.track with founders_checkout_start', () => {
    trackFoundersCheckoutStart({ email_provided: true, src: 'ribbon' });
    expect(mockTrack).toHaveBeenCalledWith('founders_checkout_start', {
      email_provided: true,
      src: 'ribbon',
    });
  });
});

describe('trackFoundersPseoConversion', () => {
  it('calls mixpanel.track with founders_pseo_conversion', () => {
    trackFoundersPseoConversion({ from_route: '/contratos/tecnologia/SP', variant: 'default' });
    expect(mockTrack).toHaveBeenCalledWith('founders_pseo_conversion', {
      from_route: '/contratos/tecnologia/SP',
      variant: 'default',
    });
  });
});

// ---------------------------------------------------------------------------
// FOUND-METRICS-001: New events
// ---------------------------------------------------------------------------

describe('trackFoundersCheckoutAbandoned', () => {
  it('calls mixpanel.track with fundadores_checkout_abandoned', () => {
    trackFoundersCheckoutAbandoned({ src: 'email' });
    expect(mockTrack).toHaveBeenCalledWith('fundadores_checkout_abandoned', { src: 'email' });
  });

  it('accepts null src', () => {
    trackFoundersCheckoutAbandoned({ src: null });
    expect(mockTrack).toHaveBeenCalledWith('fundadores_checkout_abandoned', { src: null });
  });

  it('does not throw when mixpanel.track throws', () => {
    mockTrack.mockImplementationOnce(() => {
      throw new Error('mp not initialized');
    });
    expect(() => trackFoundersCheckoutAbandoned({ src: null })).not.toThrow();
  });
});

describe('trackFoundersCheckoutError', () => {
  it('calls mixpanel.track with fundadores_checkout_error and error_message', () => {
    trackFoundersCheckoutError({ error_message: 'Falha de rede.', src: null });
    expect(mockTrack).toHaveBeenCalledWith('fundadores_checkout_error', {
      error_message: 'Falha de rede.',
      src: null,
    });
  });

  it('does not throw when mixpanel.track throws', () => {
    mockTrack.mockImplementationOnce(() => {
      throw new Error('mp not initialized');
    });
    expect(() =>
      trackFoundersCheckoutError({ error_message: 'some error' })
    ).not.toThrow();
  });
});

describe('trackFoundersInviteSent', () => {
  it('calls mixpanel.track with fundadores_invite_sent and lead_id', () => {
    trackFoundersInviteSent({ lead_id: 'abc-123' });
    expect(mockTrack).toHaveBeenCalledWith('fundadores_invite_sent', { lead_id: 'abc-123' });
  });

  it('accepts null lead_id', () => {
    trackFoundersInviteSent({ lead_id: null });
    expect(mockTrack).toHaveBeenCalledWith('fundadores_invite_sent', { lead_id: null });
  });
});

describe('trackFoundersAccountActivated', () => {
  it('calls mixpanel.track with fundadores_account_activated', () => {
    trackFoundersAccountActivated({ user_id: 'user-xyz', offer_version: 'v2_lifetime' });
    expect(mockTrack).toHaveBeenCalledWith('fundadores_account_activated', {
      user_id: 'user-xyz',
      offer_version: 'v2_lifetime',
    });
  });

  it('accepts null optional props', () => {
    trackFoundersAccountActivated({ user_id: null, offer_version: null });
    expect(mockTrack).toHaveBeenCalledWith('fundadores_account_activated', {
      user_id: null,
      offer_version: null,
    });
  });
});

describe('trackFoundersCountdownViewed', () => {
  it('calls mixpanel.track with fundadores_countdown_viewed and days_remaining', () => {
    trackFoundersCountdownViewed({ days_remaining: 23 });
    expect(mockTrack).toHaveBeenCalledWith('fundadores_countdown_viewed', { days_remaining: 23 });
  });

  it('forwards days_remaining=0 correctly', () => {
    trackFoundersCountdownViewed({ days_remaining: 0 });
    expect(mockTrack).toHaveBeenCalledWith('fundadores_countdown_viewed', { days_remaining: 0 });
  });
});
