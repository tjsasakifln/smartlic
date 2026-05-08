/**
 * Tests for email lifecycle analytics wrappers (lib/analytics/email_lifecycle.ts).
 *
 * Verifies:
 * - safeTrack swallows errors from Mixpanel (never throws)
 * - Each exported event wrapper calls mixpanel.track with the correct event
 *   name and {user_id} property
 */

import mixpanel from 'mixpanel-browser';

jest.mock('mixpanel-browser', () => ({
  __esModule: true,
  default: { track: jest.fn() },
}));

import {
  trackEmailConfirmationSent,
  trackEmailConfirmationClicked,
  trackEmailConfirmationExpired,
  trackEmailConfirmationResent,
} from '../email_lifecycle';

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

    expect(() => trackEmailConfirmationSent('user-123')).not.toThrow();
  });

  it('does not throw when mixpanel.track throws a non-Error value', () => {
    mockTrack.mockImplementationOnce(() => {
      // eslint-disable-next-line @typescript-eslint/no-throw-literal
      throw 'consent not given';
    });

    expect(() => trackEmailConfirmationClicked('user-123')).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Individual event wrappers
// ---------------------------------------------------------------------------

describe('trackEmailConfirmationSent', () => {
  it('calls mixpanel.track with email_confirmation_sent and user_id', () => {
    trackEmailConfirmationSent('user-abc-123');
    expect(mockTrack).toHaveBeenCalledWith('email_confirmation_sent', {
      user_id: 'user-abc-123',
    });
  });

  it('calls track exactly once', () => {
    trackEmailConfirmationSent('user-abc-123');
    expect(mockTrack).toHaveBeenCalledTimes(1);
  });
});

describe('trackEmailConfirmationClicked', () => {
  it('calls mixpanel.track with email_confirmation_clicked and user_id', () => {
    trackEmailConfirmationClicked('user-def-456');
    expect(mockTrack).toHaveBeenCalledWith('email_confirmation_clicked', {
      user_id: 'user-def-456',
    });
  });

  it('calls track exactly once', () => {
    trackEmailConfirmationClicked('user-def-456');
    expect(mockTrack).toHaveBeenCalledTimes(1);
  });
});

describe('trackEmailConfirmationExpired', () => {
  it('calls mixpanel.track with email_confirmation_expired and user_id', () => {
    trackEmailConfirmationExpired('user-ghi-789');
    expect(mockTrack).toHaveBeenCalledWith('email_confirmation_expired', {
      user_id: 'user-ghi-789',
    });
  });

  it('calls track exactly once', () => {
    trackEmailConfirmationExpired('user-ghi-789');
    expect(mockTrack).toHaveBeenCalledTimes(1);
  });
});

describe('trackEmailConfirmationResent', () => {
  it('calls mixpanel.track with email_confirmation_resent and user_id', () => {
    trackEmailConfirmationResent('user-jkl-012');
    expect(mockTrack).toHaveBeenCalledWith('email_confirmation_resent', {
      user_id: 'user-jkl-012',
    });
  });

  it('calls track exactly once', () => {
    trackEmailConfirmationResent('user-jkl-012');
    expect(mockTrack).toHaveBeenCalledTimes(1);
  });
});
