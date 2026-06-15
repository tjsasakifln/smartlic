/**
 * Accessibility CI Gate — 10 Critical Pages
 *
 * Scans the 10 highest-traffic pages with axe-core (WCAG 2.1 AA) as the
 * authoritative CI gate for accessibility regressions. These pages represent
 * the core user journey: acquisition (landing, login, signup, planos,
 * observatorio), activation (buscar, onboarding), and retention (pipeline,
 * conta, checkout).
 *
 * #1871 AC2 — Automated scan of 10 critical pages
 * #1871 AC4 — Zero critical or serious violations; moderate logged for triage
 * #1871 AC5 — HTML report generated as CI artifact
 *
 * Severity policy:
 *   - critical / serious  → fail the test (blocking)
 *   - moderate / minor    → logged for triage, non-blocking
 *
 * Each page test:
 *   1. Navigates to the page and waits for load
 *   2. Runs axe-core analysis with WCAG 2.1 AA tags
 *   3. Asserts zero violations at impact >= "serious"
 *   4. Attaches raw axe JSON to the Playwright report for offline triage
 *
 * @see docs/accessibility/ci-gate.md
 * @see docs/testing/a11y-e2e.md
 */

import { test } from '../fixtures/axe';
import {
  mockAuthAPI,
  mockSetoresAPI,
  mockSearchAPI,
  mockDownloadAPI,
  mockMeAPI,
} from '../helpers/test-utils';

test.describe('Critical Pages Accessibility — CI Gate', () => {
  // ===========================================================================
  // PUBLIC PAGES (no auth required)
  // ===========================================================================

  // ---------------------------------------------------------------------------
  // 1. Home / Landing page
  // ---------------------------------------------------------------------------
  test('AC1: Home page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Home');
    console.log(
      `Home: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // ---------------------------------------------------------------------------
  // 2. Login page (public)
  // ---------------------------------------------------------------------------
  test('AC2: Login page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('form', { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(500);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Login');
    console.log(
      `Login: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // ---------------------------------------------------------------------------
  // 3. Signup page (public)
  // ---------------------------------------------------------------------------
  test('AC3: Signup page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await page.goto('/signup');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('form', { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(500);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Signup');
    console.log(
      `Signup: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // ---------------------------------------------------------------------------
  // 4. Planos page (public pricing)
  // ---------------------------------------------------------------------------
  test('AC4: Planos page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await page.route('**/api/plans**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          plans: [
            {
              id: 'smartlic_pro',
              name: 'SmartLic Pro',
              price_monthly: 39700,
              price_semiannual: 35700,
              price_annual: 29700,
              features: ['1000 buscas/mês', 'Excel export', 'Pipeline'],
            },
            {
              id: 'smartlic_trial',
              name: 'Teste Grátis',
              price_monthly: 0,
              price_semiannual: 0,
              price_annual: 0,
              features: ['3 buscas', 'Preview de resultados'],
            },
          ],
        }),
      });
    });

    await page.goto('/planos');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Planos');
    console.log(
      `Planos: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // ---------------------------------------------------------------------------
  // 5. Observatório page (public, no-auth)
  // ---------------------------------------------------------------------------
  test('AC5: Observatório page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await page.goto('/observatorio');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Observatorio');
    console.log(
      `Observatório: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // ===========================================================================
  // AUTHENTICATED PAGES (require mocked auth session)
  // ===========================================================================

  // ---------------------------------------------------------------------------
  // 6. Buscar page (core search, setores + search mocks)
  // ---------------------------------------------------------------------------
  test('AC6: Buscar page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await mockAuthAPI(page, 'user');
    await mockSetoresAPI(page);
    await mockSearchAPI(page, 'success');
    await mockDownloadAPI(page);

    await page.goto('/buscar');
    await page.waitForLoadState('domcontentloaded');
    await page
      .waitForSelector('[data-testid="search-form"], form, .search-form, main', {
        timeout: 10000,
      })
      .catch(() => {});
    await page.waitForTimeout(500);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Buscar');
    console.log(
      `Buscar: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // ---------------------------------------------------------------------------
  // 7. Pipeline page (authenticated, pipeline mock)
  // ---------------------------------------------------------------------------
  test('AC7: Pipeline page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await mockAuthAPI(page, 'user');
    await mockMeAPI(page, {
      plan_id: 'smartlic_pro',
      plan_name: 'SmartLic Pro',
      credits_remaining: 50,
    });

    await page.route('**/api/pipeline**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 'pipe-1',
              titulo: 'Pregão Eletrônico - Uniformes',
              orgao: 'Prefeitura Municipal',
              valor: 150000,
              status: 'novo',
              uf: 'SP',
              data_abertura: '2026-03-15',
            },
            {
              id: 'pipe-2',
              titulo: 'Concorrência - Obras',
              orgao: 'Governo do Estado',
              valor: 2500000,
              status: 'analise',
              uf: 'RJ',
              data_abertura: '2026-04-01',
            },
          ],
          total: 2,
        }),
      });
    });

    await page.goto('/pipeline');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Pipeline');
    console.log(
      `Pipeline: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // ---------------------------------------------------------------------------
  // 8. Conta page (authenticated — account settings + billing info)
  // ---------------------------------------------------------------------------
  test('AC8: Conta page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await mockAuthAPI(page, 'user');
    await mockMeAPI(page, {
      plan_id: 'smartlic_pro',
      plan_name: 'SmartLic Pro',
      credits_remaining: 50,
    });

    await page.route('**/api/subscription**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'active',
          plan_id: 'smartlic_pro',
          plan_name: 'SmartLic Pro',
          current_period_end: '2026-04-30',
        }),
      });
    });

    await page.goto('/conta');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Conta');
    console.log(
      `Conta: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // ---------------------------------------------------------------------------
  // 9. Checkout page (authenticated — post-plan selection checkout)
  // ---------------------------------------------------------------------------
  test('AC9: Checkout page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await mockAuthAPI(page, 'user');
    await mockMeAPI(page, {
      plan_id: 'smartlic_trial',
      plan_name: 'Teste Grátis',
      credits_remaining: 3,
    });

    // Mock plans endpoint for checkout page rendering
    await page.route('**/api/plans**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          plans: [
            {
              id: 'smartlic_pro',
              name: 'SmartLic Pro',
              price_monthly: 39700,
              price_semiannual: 35700,
              price_annual: 29700,
              features: ['1000 buscas/mês', 'Excel export', 'Pipeline'],
            },
          ],
        }),
      });
    });

    // Mock Stripe checkout session setup
    await page.route('**/api/checkout**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          url: 'https://checkout.stripe.com/test-session',
          session_id: 'cs_test_mock',
        }),
      });
    });

    // Navigate to the thank-you / checkout-success page which renders after
    // a successful Stripe checkout redirect. This page is part of the core
    // post-conversion flow and must remain accessible.
    await page.goto('/planos/obrigado');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Checkout');
    console.log(
      `Checkout: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // ---------------------------------------------------------------------------
  // 10. Onboarding page (authenticated — 3-step wizard)
  // ---------------------------------------------------------------------------
  test('AC10: Onboarding page has 0 critical/serious a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await mockAuthAPI(page, 'user');
    await mockMeAPI(page, {
      plan_id: 'smartlic_pro',
      plan_name: 'SmartLic Pro',
      credits_remaining: 50,
    });

    await page.goto('/onboarding');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Onboarding');
    console.log(
      `Onboarding: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });
});
