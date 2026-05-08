/**
 * Onboarding step tagging for MS Clarity (CONV-INST-005)
 *
 * Delegates to setClarityTag which already handles:
 *   - SSR safety (typeof window check)
 *   - LGPD consent gate (analytics consent required)
 *   - Queue-before-load pattern (clarity.q)
 *
 * Never throws — safe to call unconditionally.
 *
 * Usage:
 *   import { tagOnboardingStep } from '@/lib/analytics/clarity_onboarding';
 *   tagOnboardingStep('signup_form');
 */

import { setClarityTag } from '../../app/components/ClarityAnalytics';

export type OnboardingStep =
  | 'signup_form'
  | 'email_pending'
  | 'email_confirmed'
  | 'profile_setup'
  | 'first_search'
  | 'trial_activated'
  | 'churned';

/**
 * Tag the current MS Clarity session recording with the user's onboarding step.
 * Recordings can then be filtered in the Clarity dashboard by
 * custom tag: onboarding_step = <step>.
 *
 * Never throws — safe to call unconditionally.
 *
 * AC4 note: 'churned' step detection via ARQ cron is out of scope for this PR.
 */
export function tagOnboardingStep(step: OnboardingStep): void {
  try {
    setClarityTag('onboarding_step', step);
  } catch {
    // setClarityTag is already safe but we guard here too in case of
    // unexpected issues (e.g. test mocks throwing, future refactors).
  }
}
