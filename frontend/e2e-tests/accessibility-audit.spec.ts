/**
 * DEBT-109 AC1-AC3 + TD-FE-027 (#276): Automated Accessibility Audits.
 *
 * Runs axe-core analysis on 10 core pages to detect critical/serious WCAG 2.1
 * AA violations. Refactored on 2026-05-08 to use the shared `axe` fixture
 * (`frontend/e2e-tests/fixtures/axe.ts`) so every spec gets a pre-configured
 * AxeBuilder + an opinionated severity gate.
 *
 * Severity policy:
 *   - critical / serious  → fail the test (blocking)
 *   - moderate / minor    → logged for triage, non-blocking
 *
 * Triage runbook: docs/testing/a11y-e2e.md
 */

import { test, expect } from './fixtures/axe';
import {
  mockAuthAPI,
  mockSearchAPI,
  mockSetoresAPI,
  mockDownloadAPI,
  mockMeAPI,
} from './helpers/test-utils';

test.describe('Accessibility Audits — @axe-core/playwright', () => {
  // -----------------------------------------------------------------------
  // 1. Login page (public, no auth needed)
  // -----------------------------------------------------------------------
  test('AC1.1: Login page has 0 critical a11y violations', async ({
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

  // -----------------------------------------------------------------------
  // 2. Buscar page (core search page, needs setores mock)
  // -----------------------------------------------------------------------
  test('AC1.2: Buscar page has 0 critical a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
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

  // -----------------------------------------------------------------------
  // 3. Dashboard page (authenticated)
  // -----------------------------------------------------------------------
  test('AC1.3: Dashboard page has 0 critical a11y violations', async ({
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

    await page.route('**/api/analytics**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_searches: 25,
          total_results: 150,
          searches_over_time: [],
          top_sectors: [],
          top_ufs: [],
        }),
      });
    });

    await page.route('**/api/sessions**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sessions: [], total: 0 }),
      });
    });

    await page.goto('/dashboard');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Dashboard');
    console.log(
      `Dashboard: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // -----------------------------------------------------------------------
  // 4. Pipeline page (authenticated, needs pipeline mock)
  // -----------------------------------------------------------------------
  test('AC1.4: Pipeline page has 0 critical a11y violations', async ({
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
          ],
          total: 1,
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

  // -----------------------------------------------------------------------
  // 5. Planos page (public pricing page)
  // -----------------------------------------------------------------------
  test('AC1.5: Planos page has 0 critical a11y violations', async ({
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

  // =======================================================================
  // DEBT-205 / DEBT-FE-013: Expanded from 5 to 10 pages
  // =======================================================================

  // -----------------------------------------------------------------------
  // 6. Landing page (public)
  // -----------------------------------------------------------------------
  test('AC1.6: Landing page has 0 critical a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Landing');
    console.log(
      `Landing: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // -----------------------------------------------------------------------
  // 7. Signup page (public)
  // -----------------------------------------------------------------------
  test('AC1.7: Signup page has 0 critical a11y violations', async ({
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

  // -----------------------------------------------------------------------
  // 8. Historico page (authenticated)
  // -----------------------------------------------------------------------
  test('AC1.8: Historico page has 0 critical a11y violations', async ({
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

    await page.route('**/api/sessions**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ sessions: [], total: 0 }),
      });
    });

    await page.goto('/historico');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Historico');
    console.log(
      `Historico: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });

  // -----------------------------------------------------------------------
  // 9. Conta page (authenticated — account settings)
  // -----------------------------------------------------------------------
  test('AC1.9: Conta page has 0 critical a11y violations', async ({
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

  // -----------------------------------------------------------------------
  // 10. Ajuda page (public help center)
  // -----------------------------------------------------------------------
  test('AC1.10: Ajuda page has 0 critical a11y violations', async ({
    page,
    makeAxeBuilder,
    assertNoSeriousViolations,
  }) => {
    await page.goto('/ajuda');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(500);

    const results = await makeAxeBuilder().analyze();
    const summary = assertNoSeriousViolations(results, 'Ajuda');
    console.log(
      `Ajuda: ${summary.total} total violations (${summary.serious.length} serious, ${summary.moderate.length} moderate)`,
    );
  });
});

// Re-export so consumers can `import { expect } from this spec` if needed.
export { expect };
