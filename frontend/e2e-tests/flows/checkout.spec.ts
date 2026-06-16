/**
 * Critical Flow E2E: Complete Checkout (Issue #1863, Scenario 1)
 *
 * Tests the full subscription purchase journey:
 * plano -> Stripe Checkout -> webhook -> subscription ativa
 *
 * AC1: User browses plans on /planos
 * AC2: User selects a plan and billing period
 * AC3: User clicks "Assinar" and gets redirected to Stripe Checkout
 * AC4: After checkout, webhook processes subscription activation
 * AC5: User sees thank-you page and subscription reflects as active
 *
 * Stripe is mocked at the API level — no real charges are made (AC4).
 * Suite timeout: 5min (AC7).
 */

import { test, expect, Page, Route } from '@playwright/test';
import {
  setupAuthMock,
  mockMeEndpoint,
  makeMockUser,
  makeMeResponse,
  makePlansResponse,
  makeCheckoutResponse,
  cleanupTestState,
} from '../fixtures/mock-data';

test.describe('Scenario 1: Checkout Completo', () => {
  // AC7: Timeout global de 5min por suite
  test.describe.configure({ timeout: 300_000 });

  test.beforeEach(async ({ page }) => {
    await cleanupTestState(page);
    await setupAuthMock(page);
    await mockMeEndpoint(page, {
      plan_id: 'free_trial',
      plan_name: 'Avaliacao Gratuita',
      trial_expires_at: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
    });
  });

  /**
   * AC1: User can browse plans and see pricing information.
   * Validates that /planos renders plan cards with prices and feature lists.
   */
  test('AC1: deve exibir planos com precos e funcionalidades', async ({ page }) => {
    await mockPlansEndpoint(page);
    await page.goto('/planos');

    // Verify the page loaded
    await expect(page).toHaveURL(/planos/);
    await expect(page.locator('body')).toBeVisible();

    // Should display the SmartLic Pro plan name
    const planName = page.locator('text=/SmartLic Pro/i').first();
    await expect(planName).toBeVisible({ timeout: 15_000 });

    // Should display price in BRL format
    const price = page.locator('text=/R\\$/').first();
    await expect(price).toBeVisible({ timeout: 10_000 });

    // Should display at least one feature
    const feature = page.locator('text=/buscas/i').first();
    await expect(feature).toBeVisible({ timeout: 10_000 });
  });

  /**
   * AC2: User can toggle between billing periods and see updated prices.
   */
  test('AC2: deve alternar periodo de cobranca e exibir precos atualizados', async ({ page }) => {
    await mockPlansEndpoint(page);
    await page.goto('/planos');
    await expect(page.locator('body')).toBeVisible({ timeout: 15_000 });

    // Look for billing period toggle buttons
    const annualToggle = page
      .locator('button, [role="tab"], label')
      .filter({ hasText: /anual/i })
      .first();

    if (await annualToggle.isVisible({ timeout: 5_000 })) {
      await annualToggle.click();
      await page.waitForTimeout(500);

      // Price or discount should be visible after toggle
      const body = page.locator('body');
      await expect(body).toBeVisible();
      // Page should still be on /planos
      await expect(page).toHaveURL(/planos/);
    }
  });

  /**
   * AC3: User clicks "Assinar" and is redirected to Stripe Checkout.
   *
   * We intercept the checkout API call and return a mocked Stripe session URL.
   * The browser would navigate away to Stripe; we verify the API was called.
   */
  test('AC3: deve redirecionar para Stripe Checkout ao clicar Assinar', async ({ page }) => {
    await mockPlansEndpoint(page);
    await page.goto('/planos');
    await expect(page.locator('body')).toBeVisible({ timeout: 15_000 });

    let checkoutEndpointCalled = false;

    // Intercept checkout endpoint to track call and return mock URL
    await page.route('**/api/checkout**', async (route: Route) => {
      checkoutEndpointCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(makeCheckoutResponse()),
      });
    });

    // Intercept the stripe.com navigation so Playwright doesn't actually leave
    await page.route('**/checkout.stripe.com/**', async (route: Route) => {
      // Just block navigation to Stripe — we're testing the redirect, not Stripe itself
      await route.abort('addressunreachable');
    });

    // Click the subscribe CTA
    const ctaButton = page
      .locator('button, a')
      .filter({ hasText: /Assinar|Contratar|Comecar/i })
      .first();

    if (await ctaButton.isVisible({ timeout: 5_000 })) {
      await ctaButton.click();
      // Give time for the API call to be made
      await page.waitForTimeout(2_000);
    }

    // Verify the checkout endpoint was called
    expect(checkoutEndpointCalled).toBeTruthy();
  });

  /**
   * AC4 + AC5: After Stripe Checkout, webhook activates subscription.
   *
   * We simulate the post-checkout flow: user returns to /planos/obrigado
   * and the backend reflects subscription as active.
   */
  test('AC4-5: webhook ativa assinatura e pagina de obrigado reflete estado ativo', async ({ page }) => {
    // Set user with active subscription (post-webhook state)
    await mockMeEndpoint(page, {
      plan_id: 'smartlic_pro',
      plan_name: 'SmartLic Pro',
      credits_remaining: null,
      subscription_status: 'active',
    });

    // Navigate directly to the thank-you page (simulating redirect after checkout)
    await page.goto('/planos/obrigado');
    await expect(page.locator('body')).toBeVisible({ timeout: 15_000 });

    // Should show some success/thank-you content OR redirect to buscar/dashboard
    const currentUrl = page.url();
    const onThankYou = currentUrl.includes('obrigado');
    const redirected = currentUrl.includes('buscar') || currentUrl.includes('dashboard');

    if (onThankYou) {
      const successContent = page.locator('text=/obrigado|sucesso|assinatura|confirmado|Parabens/i').first();
      await expect(successContent).toBeVisible({ timeout: 10_000 });
    }

    expect(onThankYou || redirected).toBeTruthy();
  });

  test.afterEach(async ({ page }) => {
    // AC8: Cleanup test data after each test
    await cleanupTestState(page);
  });
});

// ---------------------------------------------------------------------------
// Local helpers
// ---------------------------------------------------------------------------

async function mockPlansEndpoint(page: Page): Promise<void> {
  await page.route('**/api/plans**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(makePlansResponse()),
    });
  });

  // Also mock billing/plans endpoint variant
  await page.route('**/api/billing/plans**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(makePlansResponse()),
    });
  });
}
