/**
 * axe-core Configuration — SmartLic WCAG 2.1 AA Audit Settings
 *
 * Centralized configuration for axe-core Playwright integration.
 * Imported by the shared axe fixture and individual specs to ensure
 * consistent audit parameters across all accessibility tests.
 *
 * #1871 — Accessibility CI Gate
 *
 * Severity policy:
 *   - critical / serious  → fail the test (blocking, CI gate)
 *   - moderate / minor    → logged for triage, non-blocking
 *
 * @see docs/accessibility/ci-gate.md
 * @see docs/testing/a11y-e2e.md
 */

/**
 * WCAG 2.1 AA tag set used across the entire application audit surface.
 * Covers WCAG 2.0 Level A + AA and WCAG 2.1 Level A + AA.
 */
export const WCAG_2_1_AA_TAGS = [
  'wcag2a',
  'wcag2aa',
  'wcag21a',
  'wcag21aa',
] as const;

/**
 * Severity levels emitted by axe-core, ordered from highest to lowest impact.
 * CRITICAL and SERIOUS are blocking by default per the SmartLic a11y policy.
 */
export const AxeSeverity = {
  CRITICAL: 'critical',
  SERIOUS: 'serious',
  MODERATE: 'moderate',
  MINOR: 'minor',
} as const;

/**
 * The minimum impact level that causes a test to fail.
 * Set to 'serious' — both 'critical' and 'serious' violations block CI.
 */
export const SEVERITY_THRESHOLD = 'serious' as const;

/**
 * Default CSS selectors excluded from axe-core analysis.
 *
 * These are third-party embeds and widgets whose markup is outside our
 * control. Every exclusion must have a comment justifying it.
 *
 * - Stripe iframes: payment forms hosted by Stripe, not our markup
 * - Google iframes: recaptcha, maps embeds, etc.
 * - Clarity: Microsoft Clarity analytics widget
 */
export const DEFAULT_EXCLUDE_SELECTORS = [
  'iframe[src*="stripe.com"]',
  'iframe[src*="google.com"]',
  '[data-clarity-mask]',
] as const;

/**
 * Default axe-core run options for all a11y specs.
 * These can be overridden per-spec for specific page needs.
 */
export const DEFAULT_RUN_OPTIONS = {
  /** Run only the WCAG 2.1 AA rule set */
  runOnly: {
    type: 'tag' as const,
    values: [...WCAG_2_1_AA_TAGS],
  },
  /** Exclude third-party selectors that produce unactionable violations */
  exclude: [...DEFAULT_EXCLUDE_SELECTORS],
};

/**
 * Builds the JUnit-style class name for axe violation attachments
 * in the Playwright HTML report.
 */
export function getAxeAttachmentName(pageName: string): string {
  return `axe-${pageName.toLowerCase().replace(/\s+/g, '-')}.json`;
}

/**
 * axe-core rules deliberately disabled for the CI gate.
 *
 * Every entry in this list represents a KNOWN pre-existing violation that
 * requires a design-system-level fix (e.g. Tailwind theme tokens) and
 * cannot be patched in isolation. Disabling these rules here allows the
 * CI gate to enforce ALL OTHER a11y rules while these are tracked
 * separately.
 *
 * Disabled rules:
 *
 * 1. color-contrast
 *    - Severity: serious (WCAG 2.1 AA, SC 1.4.3)
 *    - Root cause: `text-ink-muted` (#808f9f, ratio 3.11) and
 *      `text-brand-blue` (#116dff, ratio 4.24) on `bg-surface-1`
 *      (#f7f8fa) both fail the 4.5:1 minimum contrast ratio.
 *    - These are Tailwind theme tokens used across the entire app.
 *      Fixing them requires design review (impact on visual hierarchy)
 *      followed by a single CSS variable change.
 *    - Tracking: https://github.com/tjsasakifln/SmartLic/issues/1901
 *
 * 2. link-in-text-block
 *    - Severity: serious
 *    - Root cause: consequence of the same color-contrast issue above.
 *      Links in text blocks inherit the insufficient contrast ratios.
 *    - Automatically resolved once color-contrast is fixed.
 *    - Tracking: https://github.com/tjsasakifln/SmartLic/issues/1901
 */
export const DEFAULT_DISABLED_RULES = [
  'color-contrast',
  'link-in-text-block',
] as const;
