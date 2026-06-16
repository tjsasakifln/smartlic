/**
 * TD-FE-027 (#276): Playwright axe-core fixture for WCAG 2.1 AA validation.
 *
 * #1871: Configuration centralized in axe-config.ts; fixture consumes it.
 *
 * Usage:
 *
 *   import { test, expect, AxeSeverity } from './fixtures/axe';
 *
 *   test('home is accessible', async ({ page, makeAxeBuilder, assertNoSeriousViolations }) => {
 *     await page.goto('/');
 *     await page.waitForLoadState('domcontentloaded');
 *     const results = await makeAxeBuilder().analyze();
 *     assertNoSeriousViolations(results, 'Home');
 *   });
 *
 * The fixture wraps `AxeBuilder` so every spec gets a pre-configured builder
 * (WCAG 2.1 AA tags) plus an opinionated assertion that fails the test on any
 * violation with impact >= "serious". Critical/serious are blocking; moderate
 * and minor are logged for triage but do not fail the test.
 *
 * Severity policy and triage instructions:
 *   - docs/testing/a11y-e2e.md
 *   - docs/accessibility/ci-gate.md
 *   - frontend/e2e-tests/a11y/axe-config.ts (centralized config)
 */

import { test as base, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import type { AxeResults, ImpactValue } from 'axe-core';
import {
  WCAG_2_1_AA_TAGS,
  AxeSeverity,
  DEFAULT_EXCLUDE_SELECTORS,
  DEFAULT_DISABLED_RULES,
} from '../a11y/axe-config';

// Re-export for backward compatibility — specs that import AxeSeverity
// directly from the fixture continue to work unchanged.
export { AxeSeverity, WCAG_2_1_AA_TAGS };

type AxeFixtures = {
  /**
   * Returns a fresh `AxeBuilder` already configured with WCAG 2.1 AA tags.
   * Tests can chain `.exclude()`, `.disableRules()`, etc. before `.analyze()`.
   */
  makeAxeBuilder: () => AxeBuilder;

  /**
   * Runs axe and asserts zero violations at impact >= "serious". Logs
   * moderate/minor findings to stdout for documentation purposes.
   *
   * Returns the axe results so callers can do extra assertions if needed.
   */
  assertNoSeriousViolations: (
    results: AxeResults,
    context: string,
  ) => {
    critical: AxeResults['violations'];
    serious: AxeResults['violations'];
    moderate: AxeResults['violations'];
    minor: AxeResults['violations'];
    total: number;
  };
};

export const test = base.extend<AxeFixtures>({
  makeAxeBuilder: async ({ page }, use) => {
    const builder = () => {
      const axe = new AxeBuilder({ page }).withTags([...WCAG_2_1_AA_TAGS]);
      // Exclusions from central config (#1871). Third-party widgets we don't
      // control: Stripe iframes, Google embeds, Clarity analytics.
      for (const sel of DEFAULT_EXCLUDE_SELECTORS) {
        axe.exclude(sel);
      }
      // Known pre-existing violations disabled pending design-system fix.
      // See axe-config.ts DEFAULT_DISABLED_RULES for rationale and tracking.
      for (const rule of DEFAULT_DISABLED_RULES) {
        axe.disableRules([rule]);
      }
      return axe;
    };
    await use(builder);
  },

  assertNoSeriousViolations: async ({}, use, testInfo) => {
    const assert = (results: AxeResults, context: string) => {
      const byImpact = (impact: ImpactValue) =>
        results.violations.filter((v) => v.impact === impact);
      const critical = byImpact('critical');
      const serious = byImpact('serious');
      const moderate = byImpact('moderate');
      const minor = byImpact('minor');

      // Log non-blocking findings for triage. They appear in Playwright's
      // stdout report and the JUnit log, but do not fail the test.
      if (moderate.length > 0 || minor.length > 0) {
        // eslint-disable-next-line no-console
        console.log(`\n[${context}] Non-blocking a11y findings:`);
        for (const v of [...moderate, ...minor]) {
          // eslint-disable-next-line no-console
          console.log(
            `  - [${v.impact}] ${v.id}: ${v.description} (${v.nodes.length} nodes)`,
          );
        }
      }

      // Attach raw axe output to the Playwright HTML report so triage is
      // possible without re-running the test locally.
      void testInfo.attach(`axe-${context}.json`, {
        body: JSON.stringify(results, null, 2),
        contentType: 'application/json',
      });

      // Blocking gate: zero serious + zero critical.
      expect(
        critical,
        `Critical a11y violations on ${context}: ${critical
          .map((v) => v.id)
          .join(', ')}`,
      ).toHaveLength(0);
      expect(
        serious,
        `Serious a11y violations on ${context}: ${serious
          .map((v) => v.id)
          .join(', ')}`,
      ).toHaveLength(0);

      return {
        critical,
        serious,
        moderate,
        minor,
        total: results.violations.length,
      };
    };
    await use(assert);
  },
});

export { expect };
