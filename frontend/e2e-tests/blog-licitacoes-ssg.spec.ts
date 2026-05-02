import { test, expect } from '@playwright/test';

// SEO-643: /blog/licitacoes/{setor}/{uf} pages must return 200.
// Root cause: sitemap.ts was using raw backend sector IDs (software_desenvolvimento,
// manutencao_predial, etc.) to build URLs — those 404 on the frontend which only
// accepts slugs (software, manutencao-predial, etc.).
// These tests guard against regression where slug/id normalization breaks.

const VALID_COMBOS = [
  // Frontend slug === backend ID (identity)
  { setor: 'informatica', uf: 'rr' },
  { setor: 'vestuario', uf: 'sc' },
  { setor: 'engenharia', uf: 'ba' },
  { setor: 'engenharia', uf: 'pr' },
  // Slug differs from backend ID
  { setor: 'software', uf: 'ms' },
  { setor: 'manutencao-predial', uf: 'sp' },
  { setor: 'facilities', uf: 'mg' },
  { setor: 'saude', uf: 'rj' },
  { setor: 'transporte', uf: 'rs' },
];

const INVALID_BACKEND_IDS = [
  { setor: 'software_desenvolvimento', uf: 'ms' },
  { setor: 'manutencao_predial', uf: 'sp' },
  { setor: 'servicos_prediais', uf: 'mg' },
  { setor: 'medicamentos', uf: 'rj' },
  { setor: 'transporte_servicos', uf: 'rs' },
];

test.describe('SEO-643 — /blog/licitacoes slug normalisation', () => {
  for (const { setor, uf } of VALID_COMBOS) {
    test(`/blog/licitacoes/${setor}/${uf} returns 200`, async ({ page }) => {
      const response = await page.goto(`/blog/licitacoes/${setor}/${uf}`, {
        waitUntil: 'domcontentloaded',
        timeout: 20000,
      });
      expect(response?.status()).toBe(200);
    });
  }

  for (const { setor, uf } of INVALID_BACKEND_IDS) {
    test(`/blog/licitacoes/${setor}/${uf} returns 404 (raw backend ID)`, async ({ page }) => {
      const response = await page.goto(`/blog/licitacoes/${setor}/${uf}`, {
        waitUntil: 'domcontentloaded',
        timeout: 20000,
      });
      expect(response?.status()).toBe(404);
    });
  }
});
