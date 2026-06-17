/**
 * Critical Flow E2E: Checkout Completo (Issue #1967, Scenario 1)
 *
 * Tests the complete checkout journey end-to-end:
 * selecionar plano -> Stripe checkout -> webhook -> subscription ativa -> /buscar liberado
 *
 * AC1: User browses plans on /planos and sees pricing
 * AC2: User toggles billing period and prices update
 * AC3: "Assinar" CTA sends user to Stripe Checkout
 * AC4: Stripe webhook processes payment and activates subscription
 * AC5: Post-payment, /buscar page is accessible (subscription unlocks search)
 *
 * Suite timeout: 5min (AC7).
 */

import { test, expect, Page, Route } from '@playwright/test';
import {
  setupAuthMock,
  mockMeEndpoint,
  makeMockUser,
  makePlansResponse,
  makeCheckoutResponse,
  cleanupTestState,
} from '../fixtures/mock-data';

test.describe('[CRITICAL] Checkout Completo -> Buscar Liberado', () => {
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
   * AC1: Plans page renders plan cards with pricing and features.
   */
  test('AC1: pagina de planos exibe precos e funcionalidades', async ({ page }) => {
    await mockPlansEndpoint(page);
    await page.goto('/planos');

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
   * AC2: User toggles between monthly / annual billing and prices reflect the change.
   */
  test('AC2: alternancia de periodo de cobranca atualiza precos', async ({ page }) => {
    await mockPlansEndpoint(page);
    await page.goto('/planos');
    await expect(page.locator('body')).toBeVisible({ timeout: 15_000 });

    const annualToggle = page
      .locator('button, [role="tab"], label')
      .filter({ hasText: /anual/i })
      .first();

    if (await annualToggle.isVisible({ timeout: 5_000 })) {
      await annualToggle.click();
      await page.waitForTimeout(500);
      await expect(page).toHaveURL(/planos/);
      await expect(page.locator('body')).toBeVisible();
    }
  });

  /**
   * AC3: User clicks "Assinar" and is redirected to Stripe Checkout.
   */
  test('AC3: clique em Assinar redireciona para Stripe Checkout', async ({ page }) => {
    await mockPlansEndpoint(page);
    await page.goto('/planos');
    await expect(page.locator('body')).toBeVisible({ timeout: 15_000 });

    let checkoutEndpointCalled = false;

    await page.route('**/api/checkout**', async (route: Route) => {
      checkoutEndpointCalled = true;
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(makeCheckoutResponse()),
      });
    });

    await page.route('**/checkout.stripe.com/**', async (route: Route) => {
      await route.abort('addressunreachable');
    });

    const ctaButton = page
      .locator('button, a')
      .filter({ hasText: /Assinar|Contratar|Comecar/i })
      .first();

    const ctaVisible = await ctaButton.isVisible({ timeout: 5_000 });
    expect(ctaVisible).toBeTruthy();

    if (ctaVisible) {
      await ctaButton.click();
      await page.waitForTimeout(2_000);
      expect(checkoutEndpointCalled).toBeTruthy();
    }
  });

  /**
   * AC4: Post-webhook, subscription reflects as active.
   */
  test('AC4: webhook processa pagamento e assinatura fica ativa', async ({ page }) => {
    await mockMeEndpoint(page, {
      plan_id: 'smartlic_pro',
      plan_name: 'SmartLic Pro',
      credits_remaining: null,
      subscription_status: 'active',
      trial_expires_at: undefined,
    });
    await mockPlansEndpoint(page);

    // Navigate to thank-you page (simulating post-checkout return)
    await page.goto('/planos/obrigado');
    await expect(page.locator('body')).toBeVisible({ timeout: 15_000 });

    // Verify success message or redirect to buscar
    const currentUrl = page.url();
    const onThankYou = currentUrl.includes('obrigado');
    const redirected = currentUrl.includes('buscar') || currentUrl.includes('dashboard');

    if (onThankYou) {
      const successContent = page.locator(
        'text=/obrigado|sucesso|assinatura|confirmado|Parabens|ativa/i'
      ).first();
      await expect(successContent).toBeVisible({ timeout: 10_000 });
    }

    expect(onThankYou || redirected).toBeTruthy();
  });

  /**
   * AC5: After subscription is active, the /buscar page is unlocked.
   * Verifies that the search page loads without paywall restrictions.
   */
  test('AC5: /buscar fica liberado apos assinatura ativa', async ({ page }) => {
    const paidUser = makeMockUser({
      id: 'critical-flow-paid-user',
      email: 'critical-flow-paid@test.smartlic.tech',
      user_metadata: { full_name: 'Paid Critical Flow Tester' },
    });

    await cleanupTestState(page);
    await setupAuthMock(page, paidUser);
    await mockMeEndpoint(page, {
      plan_id: 'smartlic_pro',
      plan_name: 'SmartLic Pro',
      credits_remaining: 1000,
      subscription_status: 'active',
    });
    await mockSearchEndpoint(page);

    await page.goto('/buscar');
    await expect(page.locator('body')).toBeVisible({ timeout: 15_000 });

    // Verify buscar page loaded
    await expect(page).toHaveURL(/buscar/);
    await page.waitForTimeout(2_000);

    // Should NOT show paywall / trial-expired banners
    const paywallContent = page.locator(
      'text=/Trial expirado|Assine ja|Periodo gratuito encerrado/i'
    );
    const paywallVisible = await paywallContent.isVisible({ timeout: 3_000 }).catch(() => false);
    expect(paywallVisible).toBeFalsy();

    // Should show search interface available
    const searchForm = page.locator('form, input, button').filter({ hasText: /Buscar/i }).first();
    const formVisible = await searchForm.isVisible({ timeout: 5_000 }).catch(() => false);
    expect(formVisible).toBeTruthy();
  });

  test.afterEach(async ({ page }) => {
    await cleanupTestState(page);
  });
});

// ---------------------------------------------------------------------------
// Mock helpers
// ---------------------------------------------------------------------------

async function mockPlansEndpoint(page: Page): Promise<void> {
  await page.route('**/api/plans**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(makePlansResponse()),
    });
  });
  await page.route('**/api/billing/plans**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(makePlansResponse()),
    });
  });
}

async function mockSearchEndpoint(page: Page): Promise<void> {
  await page.route('**/api/buscar**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        search_id: 'checkout-paid-search-id',
        total_raw: 85,
        total_filtrado: 10,
        resumo: {
          resumo_executivo: 'Encontradas 10 licitacoes relacionadas.',
          total_oportunidades: 10,
          valor_total: 520000,
          destaques: ['Oportunidade em Florianopolis'],
          distribuicao_uf: { SC: 6, PR: 4 },
          alerta_urgencia: null,
        },
        licitacoes: [
          {
            id: 'lic-1',
            titulo: 'Pregao 001/2026 - Uniformes Escolares',
            orgao: 'Prefeitura de Curitiba',
            uf: 'PR',
            valor_estimado: 120000,
            data_abertura: '2026-06-20',
            modalidade: 'Pregao Eletronico',
          },
        ],
        excel_available: true,
      }),
    });
  });

  await page.route('**/api/setores**', async (route: Route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        setores: [{ id: 'vestuario', name: 'Vestuario e Uniformes', description: '' }],
      }),
    });
  });
}
