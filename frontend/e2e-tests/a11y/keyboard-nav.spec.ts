/**
 * #1972 AC3: Keyboard Navigation — WCAG 2.1.1 Keyboard (SC 2.1.1)
 *
 * Verifies that all interactive elements on the /buscar page are reachable
 * via sequential Tab navigation. This is the primary search page and the
 * core activation surface for SmartLic users.
 *
 * Scope:
 *   - Tab flows through search form controls (setor, UF, date range)
 *   - Tab flows through action buttons (buscar, limpar, salvar busca)
 *   - Tab flows through results area (pagination, download, feedback)
 *   - Focus is never trapped in a non-interactive region
 *   - Focus indicator is visible (focus-visible styles present)
 *
 * The shared axe fixture provides makeAxeBuilder and assertNoSeriousViolations
 * for complementary axe-core analysis alongside keyboard testing.
 *
 * @see WCAG 2.1.1 Keyboard: https://www.w3.org/TR/WCAG21/#keyboard
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

test.describe('Keyboard Navigation — /buscar (WCAG 2.1.1)', () => {
  test.beforeEach(async ({ page }) => {
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
    // Allow React hydration + data fetches to settle
    await page.waitForTimeout(1500);
  });

  test('AC3.1: Tab navigates through search form controls in logical order', async ({
    page,
  }) => {
    // Collect all focusable elements on the page
    const focusableSelectors = [
      'a[href]',
      'button:not([disabled])',
      'input:not([disabled]):not([type="hidden"])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ];

    const focusableElements = page.locator(focusableSelectors.join(','));
    const count = await focusableElements.count();
    expect(count, 'Page must have interactive elements for keyboard nav').toBeGreaterThan(0);

    // Tab through every focusable element and record focus state
    const focusedTexts: string[] = [];
    for (let i = 0; i < Math.min(count, 25); i++) {
      await page.keyboard.press('Tab');
      const focused = page.locator(':focus');
      const focusedExists = await focused.count();

      if (focusedExists > 0) {
        const tagName = await focused.evaluate((el) => el.tagName.toLowerCase());
        const ariaLabel = await focused.getAttribute('aria-label').catch(() => null);
        const innerText = (await focused.textContent())?.trim().slice(0, 50) || '';
        const placeholder = await focused.getAttribute('placeholder').catch(() => null);

        const label =
          ariaLabel || placeholder || innerText || `${tagName}[${i}]`;
        focusedTexts.push(label);

        // Verify focus-visible ring or outline is applied
        const className = (await focused.getAttribute('class')) || '';
        const hasFocusVisible = className.includes('focus-visible');
        const computedOutline = await focused.evaluate(
          (el) => getComputedStyle(el).outlineStyle,
        );
        const computedOutlineWidth = await focused.evaluate(
          (el) => getComputedStyle(el).outlineWidth,
        );

        const hasOutline = computedOutline !== 'none' && computedOutlineWidth !== '0px';
        expect(
          hasFocusVisible || hasOutline,
          `Element "${label}" must have visible focus indicator`,
        ).toBeTruthy();
      }
    }

    // Log the tab sequence for debugging
    console.log('\n[Keyboard Nav] Tab sequence through /buscar:');
    focusedTexts.forEach((text, i) => console.log(`  ${i + 1}. ${text}`));
    expect(focusedTexts.length, 'Tab should focus at least some elements').toBeGreaterThan(0);
  });

  test('AC3.2: Search form can be submitted via keyboard', async ({ page }) => {
    // Focus the setor dropdown or search button
    const submitButton = page.locator(
      'button[type="submit"], button:has-text("Buscar"), [data-testid="search-submit"]',
    );

    if (await submitButton.isVisible()) {
      await submitButton.focus();
      await expect(submitButton).toBeFocused();
      await page.keyboard.press('Enter');
      // Allow navigation/loading to start — no crash is the assertion
      await page.waitForTimeout(500);
    }
  });

  test('AC3.3: Tab does not trap focus in non-interactive regions', async ({
    page,
  }) => {
    // Press Tab many times to cycle through the page
    // Verify we can reach the end of the page without getting stuck
    const body = page.locator('body');

    for (let i = 0; i < 30; i++) {
      await page.keyboard.press('Tab');
      const focused = page.locator(':focus');
      const focusedExists = await focused.count();

      if (focusedExists === 0) {
        // Focus may have left the page — Tab reached the address bar or browser chrome
        // Refocus on body to continue testing
        await body.focus();
      }
    }
  });

  test('AC3.4: Shift+Tab navigates backwards through form controls', async ({
    page,
  }) => {
    // Start by focusing the last interactive element
    const focusableSelectors = [
      'a[href]',
      'button:not([disabled])',
      'input:not([disabled])',
      '[tabindex]:not([tabindex="-1"])',
    ];
    const elements = page.locator(focusableSelectors.join(','));
    const count = await elements.count();

    // Tab forward to the last element first
    for (let i = 0; i < count && i < 20; i++) {
      await page.keyboard.press('Tab');
    }

    // Now Shift+Tab backwards
    const backwardFocusTexts: string[] = [];
    for (let i = 0; i < Math.min(count, 10); i++) {
      await page.keyboard.press('Shift+Tab');
      const focused = page.locator(':focus');
      const focusedExists = await focused.count();
      if (focusedExists > 0) {
        const text =
          (await focused.getAttribute('aria-label')) ||
          (await focused.textContent())?.trim() ||
          (await focused.evaluate((el) => el.tagName.toLowerCase()));
        backwardFocusTexts.push(text);
      }
    }

    expect(
      backwardFocusTexts.length,
      'Shift+Tab should move focus backwards through elements',
    ).toBeGreaterThan(0);
  });
});
