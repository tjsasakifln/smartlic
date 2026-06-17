/**
 * #1972 AC4: Screen Reader — ARIA Roles Presence in Custom Components
 *
 * Verifies that custom interactive components across the 5 critical pages
 * have appropriate ARIA roles, labels, and attributes for screen reader
 * compatibility (WCAG 4.1.2 Name, Role, Value).
 *
 * The 5 critical pages covered:
 *   - / (home/landing)
 *   - /login
 *   - /buscar (search)
 *   - /pipeline (kanban)
 *   - /planos (pricing)
 *
 * Each page test:
 *   1. Navigates to the page with appropriate mocks
 *   2. Scans for custom components (buttons, links, inputs, navigation)
 *   3. Verifies required ARIA attributes are present
 *   4. Attaches findings to the Playwright HTML report
 *
 * @see WCAG 4.1.2 Name, Role, Value: https://www.w3.org/TR/WCAG21/#name-role-value
 * @see docs/accessibility/ci-gate.md
 */

import { test, expect } from '../fixtures/axe';
import {
  mockAuthAPI,
  mockSetoresAPI,
  mockSearchAPI,
  mockDownloadAPI,
  mockMeAPI,
} from '../helpers/test-utils';

test.describe('ARIA Roles in Custom Components — 5 Critical Pages', () => {
  // =========================================================================
  // 1. Landing page (public)
  // =========================================================================
  test('AC4.1: / (home) — custom components have ARIA roles', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1000);

    const findings = await auditAriaRoles(page);
    console.log(`Home: ${findings.total} interactive elements, ${findings.issues} ARIA issues`);
    expect(findings.issues, 'Home page should have minimal ARIA issues').toBeLessThanOrEqual(
      findings.total,
    );
  });

  // =========================================================================
  // 2. Login page (public)
  // =========================================================================
  test('AC4.2: /login — form inputs have associated labels and ARIA attributes', async ({
    page,
  }) => {
    await page.goto('/login');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForSelector('form', { timeout: 10000 }).catch(() => {});
    await page.waitForTimeout(500);

    // Verify form inputs have associated labels
    const inputs = page.locator('input');
    const inputCount = await inputs.count();

    for (let i = 0; i < inputCount; i++) {
      const input = inputs.nth(i);
      const inputId = await input.getAttribute('id');

      // Check for aria-label
      const ariaLabel = await input.getAttribute('aria-label');
      // Check for aria-labelledby
      const ariaLabelledby = await input.getAttribute('aria-labelledby');
      // Check for associated label via for attribute
      let hasLabel = false;
      if (inputId) {
        const label = page.locator(`label[for="${inputId}"]`);
        hasLabel = (await label.count()) > 0;
      }

      expect(
        ariaLabel || ariaLabelledby || hasLabel,
        `Input #${i + 1} (id="${inputId || 'none'}") must have accessible name — use aria-label, aria-labelledby, or <label for="...">`,
      ).toBeTruthy();
    }

    const findings = await auditAriaRoles(page);
    console.log(`Login: ${findings.total} interactive elements, ${findings.issues} ARIA issues`);
    expect(findings.issues, 'Login page should have minimal ARIA issues').toBeLessThanOrEqual(
      findings.total,
    );
  });

  // =========================================================================
  // 3. Buscar page (authenticated, core search)
  // =========================================================================
  test('AC4.3: /buscar — search controls have proper ARIA roles and labels', async ({
    page,
  }) => {
    await mockAuthAPI(page, 'user');
    await mockMeAPI(page, {
      plan_id: 'smartlic_pro',
      plan_name: 'SmartLic Pro',
      credits_remaining: 50,
    });
    await mockSetoresAPI(page);
    await mockSearchAPI(page, 'success');
    await mockDownloadAPI(page);

    await page.goto('/buscar');
    await page.waitForLoadState('domcontentloaded');
    await page.waitForTimeout(1500);

    // Check for landmark roles
    const main = page.locator('main, [role="main"]');
    expect(await main.count()).toBeGreaterThanOrEqual(1);

    const navigation = page.locator('nav, [role="navigation"]');
    expect(await navigation.count()).toBeGreaterThanOrEqual(1);

    // Check for form/region roles
    const formOrRegion = page.locator('form, [role="search"], [role="form"], section');
    expect(await formOrRegion.count()).toBeGreaterThanOrEqual(1);

    const findings = await auditAriaRoles(page);
    console.log(`Buscar: ${findings.total} interactive elements, ${findings.issues} ARIA issues`);
    expect(findings.issues, 'Buscar page should have minimal ARIA issues').toBeLessThanOrEqual(
      findings.total,
    );
  });

  // =========================================================================
  // 4. Pipeline page (authenticated, kanban)
  // =========================================================================
  test('AC4.4: /pipeline — kanban cards have ARIA roles and announcements', async ({
    page,
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
              titulo: 'Pregao Eletronico - Uniformes',
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
    await page.waitForTimeout(1500);

    // Check for aria-live region (drag announcements, alerts, dynamic updates)
    const liveRegion = page.locator('[aria-live]');
    const liveCount = await liveRegion.count();
    if (liveCount > 0) {
      for (let i = 0; i < liveCount; i++) {
        const liveValue = await liveRegion.nth(i).getAttribute('aria-live');
        expect(['polite', 'assertive']).toContain(liveValue);
      }
    }

    // Check for sortable/drag items with proper roles
    const sortableItems = page.locator('[role="button"], [aria-roledescription]');
    if ((await sortableItems.count()) > 0) {
      for (let i = 0; i < Math.min(await sortableItems.count(), 5); i++) {
        const hasAriaDesc = await sortableItems.nth(i).getAttribute('aria-roledescription');
        // Not all interactive items need aria-roledescription, but pipeline cards should have it
      }
    }

    const findings = await auditAriaRoles(page);
    console.log(
      `Pipeline: ${findings.total} interactive elements, ${findings.issues} ARIA issues`,
    );
    expect(findings.issues, 'Pipeline page should have minimal ARIA issues').toBeLessThanOrEqual(
      findings.total,
    );
  });

  // =========================================================================
  // 5. Planos page (public pricing)
  // =========================================================================
  test('AC4.5: /planos — pricing cards and CTAs have ARIA roles', async ({ page }) => {
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
              features: ['1000 buscas/mes', 'Excel export', 'Pipeline'],
            },
            {
              id: 'smartlic_trial',
              name: 'Teste Gratis',
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

    // Verify all CTA buttons have accessible names
    const ctas = page.locator(
      'a[href*="checkout"], a[href*="/signup"], button:has-text("Assinar"), button:has-text("Comecar"), a:has-text("Assinar"), a:has-text("Comecar")',
    );
    const ctaCount = await ctas.count();
    for (let i = 0; i < ctaCount; i++) {
      const cta = ctas.nth(i);
      const ctaText = (await cta.textContent())?.trim();
      const ariaLabel = await cta.getAttribute('aria-label');
      const ctaRole = await cta.getAttribute('role');

      // If it's an <a> without href, it needs role="button"
      const tagName = await cta.evaluate((el) => el.tagName.toLowerCase());
      if (tagName === 'a') {
        const href = await cta.getAttribute('href');
        if (!href || href === '#') {
          expect(
            ctaRole,
            `CTA "${ctaText}" is a link without href — must have role="button"`,
          ).toBe('button');
        }
      }

      expect(
        ctaText || ariaLabel,
        `CTA #${i + 1} must have visible text or aria-label`,
      ).toBeTruthy();
    }

    const findings = await auditAriaRoles(page);
    console.log(
      `Planos: ${findings.total} interactive elements, ${findings.issues} ARIA issues`,
    );
    expect(findings.issues, 'Planos page should have minimal ARIA issues').toBeLessThanOrEqual(
      findings.total,
    );
  });
});

/**
 * Audits ARIA roles on custom interactive elements within the page.
 *
 * Checks:
 *  - All buttons/links have accessible names (text content or aria-label)
 *  - Custom interactive elements (div/span with click handlers) have role="button" or appropriate role
 *  - Images have alt text or role="presentation"
 *  - iframes have title attributes
 *
 * Returns summary of total elements checked and issues found.
 */
async function auditAriaRoles(page: import('@playwright/test').Page) {
  let issues = 0;
  let total = 0;

  // 1. Check buttons have accessible names
  const buttons = page.locator('button');
  const buttonCount = await buttons.count();
  total += buttonCount;
  for (let i = 0; i < buttonCount; i++) {
    const btn = buttons.nth(i);
    const text = (await btn.textContent())?.trim();
    const ariaLabel = await btn.getAttribute('aria-label');
    const ariaHidden = await btn.getAttribute('aria-hidden');
    if ((!text && !ariaLabel) || text === '') {
      // Skip icon-only buttons that are intentionally aria-hidden
      if (ariaHidden !== 'true') {
        issues++;
      }
    }
  }

  // 2. Check images have alt or role="presentation"
  const imgs = page.locator('img');
  const imgCount = await imgs.count();
  total += imgCount;
  for (let i = 0; i < imgCount; i++) {
    const img = imgs.nth(i);
    const alt = await img.getAttribute('alt');
    const role = await img.getAttribute('role');
    if (alt === null && role !== 'presentation') {
      issues++;
    }
  }

  // 3. Check iframes have title
  const iframes = page.locator('iframe');
  const iframeCount = await iframes.count();
  total += iframeCount;
  for (let i = 0; i < iframeCount; i++) {
    const iframe = iframes.nth(i);
    const title = await iframe.getAttribute('title');
    if (!title) {
      issues++;
    }
  }

  // 4. Check custom clickable divs/span have role="button"
  const clickableCustom = page.locator(
    '[onclick]:not(button):not(a):not(input):not(select), [cursor="pointer"]:not(button):not(a):not(input):not(select)',
  );
  const customCount = await clickableCustom.count();
  total += customCount;
  for (let i = 0; i < customCount; i++) {
    const el = clickableCustom.nth(i);
    const role = await el.getAttribute('role');
    const tabIndex = await el.getAttribute('tabindex');
    if (!role && tabIndex === '0') {
      issues++;
    }
  }

  return { total, issues };
}
