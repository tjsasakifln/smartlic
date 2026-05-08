/**
 * Tests for MS Clarity onboarding step tagging (lib/analytics/clarity_onboarding.ts).
 *
 * Verifies:
 * - tagOnboardingStep does not throw when window.clarity is undefined
 * - tagOnboardingStep calls window.clarity('set', 'onboarding_step', step) when available
 * - All OnboardingStep literal values are type-safe and exercised
 *
 * Strategy: mock setClarityTag (the underlying primitive) so tests don't depend
 * on LGPD consent or ClarityAnalytics internals.
 */

// Mock the ClarityAnalytics module before importing the module under test
jest.mock('../../../app/components/ClarityAnalytics', () => ({
  setClarityTag: jest.fn(),
  getCookieConsent: jest.fn(() => ({ analytics: true })),
}));

import { setClarityTag } from '../../../app/components/ClarityAnalytics';
import { tagOnboardingStep, type OnboardingStep } from '../clarity_onboarding';

const mockSetClarityTag = setClarityTag as jest.Mock;

beforeEach(() => {
  mockSetClarityTag.mockClear();
});

// ---------------------------------------------------------------------------
// Safety — never throws
// ---------------------------------------------------------------------------

describe('tagOnboardingStep safety', () => {
  it('does not throw when setClarityTag is called', () => {
    expect(() => tagOnboardingStep('signup_form')).not.toThrow();
  });

  it('does not throw for any valid OnboardingStep', () => {
    const steps: OnboardingStep[] = [
      'signup_form',
      'email_pending',
      'email_confirmed',
      'profile_setup',
      'first_search',
      'trial_activated',
      'churned',
    ];
    steps.forEach(step => {
      expect(() => tagOnboardingStep(step)).not.toThrow();
    });
  });

  it('does not throw when setClarityTag throws internally', () => {
    mockSetClarityTag.mockImplementationOnce(() => {
      throw new Error('Clarity not loaded');
    });
    expect(() => tagOnboardingStep('signup_form')).not.toThrow();
  });
});

// ---------------------------------------------------------------------------
// Correct delegation — calls setClarityTag with the right key/value
// ---------------------------------------------------------------------------

describe('tagOnboardingStep delegation', () => {
  it('calls setClarityTag with key "onboarding_step" and the step value', () => {
    tagOnboardingStep('signup_form');
    expect(mockSetClarityTag).toHaveBeenCalledWith('onboarding_step', 'signup_form');
  });

  it('calls setClarityTag exactly once per invocation', () => {
    tagOnboardingStep('email_pending');
    expect(mockSetClarityTag).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// All step values delegate correctly
// ---------------------------------------------------------------------------

describe('OnboardingStep — all values delegate to setClarityTag', () => {
  const steps: OnboardingStep[] = [
    'signup_form',
    'email_pending',
    'email_confirmed',
    'profile_setup',
    'first_search',
    'trial_activated',
    'churned',
  ];

  steps.forEach(step => {
    it(`delegates step "${step}" correctly`, () => {
      tagOnboardingStep(step);
      expect(mockSetClarityTag).toHaveBeenCalledWith('onboarding_step', step);
    });
  });
});
