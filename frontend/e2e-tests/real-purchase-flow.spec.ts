/**
 * REAL PURCHASE FLOW — E2E Measurement Test
 *
 * Simula um usuario real do clique ao recebimento do produto.
 * NAO USA MOCKS — vai contra producao real com Stripe live.
 *
 * Objetivo: medir onde o usuario cairia fora no fluxo de compra.
 *
 * Uso:
 *   FRONTEND_URL=https://smartlic.tech npx playwright test e2e-tests/real-purchase-flow.spec.ts --headed
 *
 * Pre-requisitos:
 *   - Cupom E2E100OFF (100% off) criado no Stripe
 *   - Usuario e2e-flow-test@smartlic.tech criado e confirmado
 *
 * NAO RODA EM CI — apenas manual com --headed para debug visual.
 */

import { test, expect } from '@playwright/test';
import * as path from 'path';
import * as fs from 'fs';

// ─── Config ────────────────────────────────────────────────────────────────
const CONFIG = {
  email: 'e2e-flow-test@smartlic.tech',
  password: 'E2ETest123!@#Flow',
  couponCode: 'E2E100OFF',
  stripeCheckoutTimeout: 60_000,
  webhookProcessingTimeout: 90_000,
};

// ─── Tipos ─────────────────────────────────────────────────────────────────
interface StepMetric {
  step: string;
  status: 'pass' | 'fail' | 'skip' | 'warn';
  durationMs: number;
  notes: string;
  screenshot?: string;
  droppedHere?: boolean;
}

interface FlowReport {
  flowName: string;
  startedAt: string;
  finishedAt: string;
  totalDurationMs: number;
  steps: StepMetric[];
  dropoffPoint: string | null;
  summary: string;
}

// ─── Helpers ───────────────────────────────────────────────────────────────

const screenshotsDir = path.resolve(
  process.env.E2E_SCREENSHOTS_DIR || './test-results/real-purchase-screenshots'
);

function ensureDir(dir: string) {
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
}

class FlowMeasurer {
  private steps: StepMetric[] = [];
  private flowStart: number;
  flowName: string;

  constructor(flowName: string) {
    this.flowName = flowName;
    this.flowStart = Date.now();
    ensureDir(screenshotsDir);
  }

  async measure(
    page: import('@playwright/test').Page,
    stepName: string,
    action: () => Promise<void>,
    opts?: { takeScreenshot?: boolean; expectNavigation?: boolean }
  ): Promise<StepMetric> {
    const start = Date.now();
    let status: StepMetric['status'] = 'pass';
    let notes = '';
    let screenshotPath: string | undefined;

    try {
      if (opts?.expectNavigation) {
        await Promise.all([page.waitForLoadState('networkidle'), action()]);
      } else {
        await action();
      }
    } catch (err: any) {
      status = 'fail';
      notes = err.message?.slice(0, 200) || String(err);
    }

    const durationMs = Date.now() - start;

    if (opts?.takeScreenshot && status !== 'fail') {
      const safe = stepName.replace(/[^a-zA-Z0-9]/g, '-');
      const filename = `${this.flowName}-${safe}.png`;
      screenshotPath = path.join(screenshotsDir, filename);
      try {
        await page.screenshot({ path: screenshotPath, fullPage: false });
      } catch {
        // non-critical
      }
    }

    const metric: StepMetric = {
      step: stepName,
      status,
      durationMs,
      notes,
      screenshot: screenshotPath,
    };

    this.steps.push(metric);
    return metric;
  }

  getSteps() {
    return this.steps;
  }

  generateReport(): FlowReport {
    const totalDuration = Date.now() - this.flowStart;
    const failedSteps = this.steps.filter((s) => s.status === 'fail');
    const dropoffIndex = this.steps.findIndex(
      (s) => s.status === 'fail' || s.droppedHere
    );
    const dropoffPoint =
      dropoffIndex >= 0 ? this.steps[dropoffIndex].step : null;

    // Qualquer step > 5s eh ponto de friccao
    const slowSteps = this.steps.filter((s) => s.durationMs > 5000);
    for (const s of slowSteps) {
      if (s.status === 'pass') s.droppedHere = true;
    }

    let summary: string;
    if (failedSteps.length > 0) {
      summary = `QUEBRA em "${failedSteps[0].step}": ${failedSteps[0].notes}`;
    } else if (slowSteps.length > 0) {
      const names = slowSteps.map((s) => `${s.step} (${(s.durationMs / 1000).toFixed(1)}s)`).join(', ');
      summary = `COMPLETO mas com FRICCAO em: ${names}`;
    } else {
      summary = `COMPLETO sem friccao — todos os passos <5s`;
    }

    return {
      flowName: this.flowName,
      startedAt: new Date(this.flowStart).toISOString(),
      finishedAt: new Date().toISOString(),
      totalDurationMs: totalDuration,
      steps: this.steps,
      dropoffPoint,
      summary,
    };
  }
}

function logReport(report: FlowReport) {
  console.log('\n' + '='.repeat(72));
  console.log(`REPORT: ${report.flowName}`);
  console.log('='.repeat(72));
  console.log(`Start:     ${report.startedAt}`);
  console.log(`End:       ${report.finishedAt}`);
  console.log(`Duration:  ${(report.totalDurationMs / 1000).toFixed(1)}s`);
  console.log(`Drop-off:  ${report.dropoffPoint || 'NONE'}`);
  console.log(`Summary:   ${report.summary}`);
  console.log('-'.repeat(72));
  for (const s of report.steps) {
    const icon = s.status === 'pass' ? 'OK' : s.status === 'fail' ? 'XX' : s.status === 'warn' ? '!!' : '--';
    const dropped = s.droppedHere ? ' DROP-OFF' : '';
    console.log(`  ${icon} ${s.step.padEnd(38)} ${(s.durationMs / 1000).toFixed(1).padStart(5)}s${dropped}`);
    if (s.notes) console.log(`     ${s.notes}`);
  }
  console.log('='.repeat(72));

  const screenshotsTaken = report.steps.filter((s) => s.screenshot);
  if (screenshotsTaken.length > 0) {
    console.log(`Screenshots (${screenshotsTaken.length}): ${screenshotsDir}`);
  }

  const reportPath = path.join(screenshotsDir, `${report.flowName}-report.json`);
  fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
  console.log(`JSON report: ${reportPath}`);
}

// ═══════════════════════════════════════════════════════════════════════════
// TESTE 1: CNPJ -> Intel Report Raio-X (R$197)
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Real Purchase: CNPJ -> Raio-X (R$197)', () => {
  test.setTimeout(300_000);

  test('Fluxo completo', async ({ page }) => {
    const m = new FlowMeasurer('cnpj-raio-x');
    const baseUrl = process.env.FRONTEND_URL || 'https://smartlic.tech';

    // STEP 0: Login
    await m.measure(page, '0-login-page', async () => {
      await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' });
    }, { takeScreenshot: true });

    const alreadyLoggedIn = await page.evaluate(() => {
      return document.cookie.includes('sb-fqqyovlzdzimiwfofdjk-auth-token');
    });

    if (!alreadyLoggedIn) {
      await m.measure(page, '0a-fill-email', async () => {
        await page.fill('input[type="email"]', CONFIG.email);
      });
      await m.measure(page, '0b-fill-password', async () => {
        await page.fill('input[type="password"]', CONFIG.password);
      });
      await m.measure(page, '0c-submit-login', async () => {
        await page.click('button[type="submit"]');
        await page.waitForURL('**/buscar**', { timeout: 15_000 });
      });
      await m.measure(page, '0d-post-login', async () => {
        await page.waitForLoadState('networkidle');
      }, { takeScreenshot: true });
    } else {
      await m.measure(page, '0-skip-already-logged-in', async () => {
        await page.goto(`${baseUrl}/buscar`, { waitUntil: 'networkidle' });
      });
    }

    // STEP 1: Navigate to CNPJ page
    const cnpj = '00360305000104';
    await m.measure(page, '1-cnpj-page', async () => {
      await page.goto(`${baseUrl}/cnpj/${cnpj}`, {
        waitUntil: 'networkidle',
        timeout: 30_000,
      });
    }, { takeScreenshot: true });

    // STEP 2: Find CTA button
    const cta = page.locator('button, a', {
      hasText: /Comprar Raio-X|Comprar Relatorio/i,
    });
    await m.measure(page, '2-find-cta', async () => {
      await cta.first().waitFor({ state: 'visible', timeout: 15_000 });
    });

    // STEP 3: Click CTA -> Stripe Checkout
    await m.measure(page, '3-click-cta', async () => {
      await cta.first().click();
      await page.waitForURL(/checkout\.stripe\.com/, { timeout: 30_000 });
    });

    // STEP 4: Stripe Checkout - apply coupon
    await m.measure(page, '4-stripe-loaded', async () => {
      await page.waitForLoadState('networkidle');
    }, { takeScreenshot: true });

    // Try to apply coupon
    const addPromo = page.locator('button, a', {
      hasText: /Adicionar|Promo|Cupom|Discount|promo/i,
    });
    const promoVisible = await addPromo.isVisible({ timeout: 3000 }).catch(() => false);
    if (promoVisible) {
      await m.measure(page, '4a-click-add-promo', async () => {
        await addPromo.first().click();
        await page.waitForTimeout(1000);
      });
      await m.measure(page, '4b-fill-coupon', async () => {
        const input = page.locator('input').first();
        await input.fill(CONFIG.couponCode);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(2000);
      });
      await m.measure(page, '4c-coupon-applied', async () => {
        await page.waitForTimeout(1000);
      }, { takeScreenshot: true });
    } else {
      // Tenta achar campo de promocao direto
      const promoInput = page.locator('#promo-code, [name="promoCode"], [data-testid="promo-code-input"]');
      const promoInputVisible = await promoInput.isVisible({ timeout: 2000 }).catch(() => false);
      if (promoInputVisible) {
        await m.measure(page, '4a-fill-coupon-direct', async () => {
          await promoInput.fill(CONFIG.couponCode);
          await page.keyboard.press('Enter');
          await page.waitForTimeout(2000);
        });
      } else {
        const lastStep = m.getSteps()[m.getSteps().length - 1];
        lastStep.notes = 'Campo de promocao nao encontrado no Stripe Checkout';
      }
    }

    // STEP 5: Pay
    const payBtn = page.locator('button[type="submit"]', {
      hasText: /Pagar|Pay|Confirmar|Submit|Comprar/i,
    });
    await m.measure(page, '5-click-pay', async () => {
      await payBtn.first().click();
      await page.waitForURL(/smartlic\.tech/, { timeout: 60_000 });
    });

    // STEP 6: Post-purchase confirmation
    await m.measure(page, '6-confirmation', async () => {
      await page.waitForLoadState('networkidle');
    }, { takeScreenshot: true });

    const url = page.url();
    const isSuccess = url.includes('intel-reports') || url.includes('obrigado');
    if (isSuccess) {
      await m.measure(page, '6a-poll-status', async () => {
        const success = page.locator(
          'text=sucesso, text=confirmado, text=obrigado, text=pronto, text=download, text=Download'
        );
        await success.first().waitFor({ state: 'visible', timeout: 60_000 });
      });
    }

    const report = m.generateReport();
    logReport(report);

    const reached = report.steps.some(
      (s) => s.step === '6-confirmation' && s.status === 'pass'
    );
    expect(reached, 'Deve chegar a pagina de confirmacao').toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// TESTE 2: Blog -> ContextualCapture -> PartialReportPreview (R$47)
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Real Purchase: Blog -> Relatorio (R$47)', () => {
  test.setTimeout(300_000);

  test('Fluxo completo', async ({ page }) => {
    const m = new FlowMeasurer('blog-relatorio');
    const baseUrl = process.env.FRONTEND_URL || 'https://smartlic.tech';

    // STEP 0: Login
    await m.measure(page, '0-login', async () => {
      await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' });
      const loggedIn = await page.evaluate(() =>
        document.cookie.includes('sb-fqqyovlzdzimiwfofdjk-auth-token')
      );
      if (!loggedIn) {
        await page.fill('input[type="email"]', CONFIG.email);
        await page.fill('input[type="password"]', CONFIG.password);
        await page.click('button[type="submit"]');
        await page.waitForURL('**/buscar**', { timeout: 15_000 });
      }
    });

    // STEP 1: Navigate to blog listing
    await m.measure(page, '1-blog-listing', async () => {
      await page.goto(`${baseUrl}/blog`, { waitUntil: 'networkidle' });
    }, { takeScreenshot: true });

    // STEP 2: Click first article
    await m.measure(page, '2-click-article', async () => {
      const link = page.locator('a[href*="/blog/"]').first();
      await link.click();
      await page.waitForLoadState('networkidle');
    }, { takeScreenshot: true });

    // STEP 3: Scroll to 60% to trigger ContextualCapture
    await m.measure(page, '3-scroll-60pct', async () => {
      await page.evaluate(async () => {
        const h = document.body.scrollHeight;
        for (let i = 0; i <= 12; i++) {
          window.scrollTo(0, (h / 20) * i);
          await new Promise((r) => setTimeout(r, 300));
        }
      });
      await page.waitForTimeout(2000);
    }, { takeScreenshot: true });

    // STEP 4: Handle email gate
    const emailInput = page.locator('input[type="email"]');
    const hasEmailGate = await emailInput.isVisible({ timeout: 3000 }).catch(() => false);
    if (hasEmailGate) {
      await m.measure(page, '4-fill-email-gate', async () => {
        await emailInput.first().fill(CONFIG.email);
        await page.locator('button[type="submit"]').first().click();
        await page.waitForTimeout(3000);
      });
    } else {
      await m.measure(page, '4-skip-email-gate', async () => {
        // Usuario logado pode pular email gate
      });
    }

    // STEP 5: Find report preview CTA
    await m.measure(page, '5-report-preview', async () => {
      const preview = page.locator('button, a', {
        hasText: /Comprar|R\$\s*47|R\$\s*67/i,
      });
      await preview.first().waitFor({ state: 'visible', timeout: 15_000 });
    }, { takeScreenshot: true });

    // STEP 6: Click buy -> Stripe
    const buyBtn = page.locator('button, a', {
      hasText: /Comprar|R\$\s*47/i,
    });
    await m.measure(page, '6-click-buy', async () => {
      await buyBtn.first().click();
      await page.waitForURL(/checkout\.stripe\.com/, { timeout: 30_000 });
    });

    // STEP 7: Stripe Checkout
    await m.measure(page, '7-stripe-checkout', async () => {
      await page.waitForLoadState('networkidle');
    }, { takeScreenshot: true });

    // Apply coupon
    const addPromo = page.locator('button, a', {
      hasText: /Adicionar|Promo|Cupom|Discount|promo/i,
    });
    const promoVisible = await addPromo.isVisible({ timeout: 3000 }).catch(() => false);
    if (promoVisible) {
      await m.measure(page, '7a-add-promo', async () => {
        await addPromo.first().click();
        await page.waitForTimeout(1000);
      });
      await m.measure(page, '7b-fill-coupon', async () => {
        const input = page.locator('input').first();
        await input.fill(CONFIG.couponCode);
        await page.keyboard.press('Enter');
        await page.waitForTimeout(2000);
      });
    }

    // STEP 8: Pay
    const payBtn = page.locator('button[type="submit"]', {
      hasText: /Pagar|Pay|Confirmar|Submit|Comprar/i,
    });
    await m.measure(page, '8-click-pay', async () => {
      await payBtn.first().click();
      await page.waitForURL(/smartlic\.tech/, { timeout: 60_000 });
    });

    // STEP 9: Confirmation
    await m.measure(page, '9-confirmation', async () => {
      await page.waitForLoadState('networkidle');
    }, { takeScreenshot: true });

    const report = m.generateReport();
    logReport(report);

    const reached = report.steps.some(
      (s) => s.step === '9-confirmation' && s.status === 'pass'
    );
    expect(reached, 'Deve chegar a pagina de confirmacao').toBe(true);
  });
});
