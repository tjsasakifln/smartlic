/**
 * Typed Mixpanel analytics wrappers for email confirmation lifecycle events.
 *
 * All functions are safe to call unconditionally — they never throw even if
 * Mixpanel is not initialized (SSR, consent not given, token missing).
 *
 * Import pattern:
 *   import { trackEmailConfirmationSent } from '@/lib/analytics/email_lifecycle';
 *
 * Events covered (CONV-INST-003):
 *   - email_confirmation_sent
 *   - email_confirmation_clicked
 *   - email_confirmation_expired
 *   - email_confirmation_resent
 */

import mixpanel from 'mixpanel-browser';

// Safe wrapper — never throws even if Mixpanel not initialized
function safeTrack(event: string, props?: Record<string, unknown>): void {
  try {
    mixpanel.track(event, props);
  } catch {
    // Mixpanel not initialized (SSR or consent not given)
  }
}

// ============================================================
// Email Confirmation Lifecycle Events
// ============================================================

/**
 * Fire when a confirmation email is sent to the user after signup.
 */
export function trackEmailConfirmationSent(userId: string): void {
  safeTrack('email_confirmation_sent', { user_id: userId });
}

/**
 * Fire when the user clicks the confirmation link in the email.
 */
export function trackEmailConfirmationClicked(userId: string): void {
  safeTrack('email_confirmation_clicked', { user_id: userId });
}

/**
 * Fire when an unconfirmed email confirmation link expires.
 */
export function trackEmailConfirmationExpired(userId: string): void {
  safeTrack('email_confirmation_expired', { user_id: userId });
}

/**
 * Fire when the user requests a resend of the confirmation email.
 */
export function trackEmailConfirmationResent(userId: string): void {
  safeTrack('email_confirmation_resent', { user_id: userId });
}
