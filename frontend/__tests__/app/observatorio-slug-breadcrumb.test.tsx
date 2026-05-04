/**
 * Issue #658: /observatorio/[slug] breadcrumb visual + JSON-LD BreadcrumbList +
 * canonical on noindex branch.
 *
 * Asserts:
 * - generateMetadata: noindex branch (missing payload) emits explicit canonical
 *   to its own URL (não herda root).
 * - Page render: <nav aria-label="Breadcrumb"> presente.
 * - Page render: JSON-LD script com "@type": "BreadcrumbList" e 3 ListItems.
 */

import { render } from '@testing-library/react';
import React from 'react';

// Mock client component to avoid Recharts/SSR deps in test render
jest.mock('@/app/observatorio/[slug]/ObservatorioRelatorioClient', () => {
  const Mock = () => <div data-testid="observatorio-client" />;
  Mock.displayName = 'ObservatorioRelatorioClientMock';
  return { __esModule: true, default: Mock };
});

jest.mock('@sentry/nextjs', () => ({
  captureMessage: jest.fn(),
}));

const mockRelatorio = {
  mes: 3,
  ano: 2026,
  mes_nome: 'março',
  periodo: 'Editais publicados de 1 a 31 de março de 2026',
  total_editais: 12543,
  valor_total: 1580000000,
  valor_medio: 125000,
  top_ufs: [],
  modalidades: [],
  tendencia_semanal: [],
  setores_em_alta: [],
  gerado_em: '2026-04-01T10:00:00Z',
  fonte: 'SmartLic Observatório — dados PNCP',
  license: 'Creative Commons BY 4.0',
};

global.fetch = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
  (global.fetch as jest.Mock).mockResolvedValue({
    ok: true,
    json: async () => mockRelatorio,
  });
});

// ---------------------------------------------------------------------------
// generateMetadata — canonical em branch noindex (Issue #658)
// ---------------------------------------------------------------------------

describe('generateMetadata — canonical no branch noindex (Issue #658)', () => {
  it('payload vazio gera canonical explícito para a própria URL', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...mockRelatorio, total_editais: 0 }),
    });
    const { generateMetadata } = await import('@/app/observatorio/[slug]/page');
    const meta = await generateMetadata({
      params: Promise.resolve({ slug: 'raio-x-marco-2026' }),
    });
    expect(meta.alternates?.canonical).toBe(
      'https://smartlic.tech/observatorio/raio-x-marco-2026',
    );
    // Continua noindex mas follow=true (canonical+noindex é sinal Google válido).
    const robots = meta.robots as { index?: boolean; follow?: boolean } | undefined;
    expect(robots?.index).toBe(false);
    expect(robots?.follow).toBe(true);
  });

  it('fetch retorna null → canonical explícito mantido', async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: false });
    const { generateMetadata } = await import('@/app/observatorio/[slug]/page');
    const meta = await generateMetadata({
      params: Promise.resolve({ slug: 'raio-x-abril-2026' }),
    });
    expect(meta.alternates?.canonical).toBe(
      'https://smartlic.tech/observatorio/raio-x-abril-2026',
    );
  });
});

// ---------------------------------------------------------------------------
// Page render — visual breadcrumb + JSON-LD BreadcrumbList (Issue #658)
// ---------------------------------------------------------------------------

describe('RelatorioPage render — breadcrumb visual + JSON-LD (Issue #658)', () => {
  it('renderiza <nav aria-label="Breadcrumb"> e JSON-LD BreadcrumbList com 3 ListItem', async () => {
    const PageMod = await import('@/app/observatorio/[slug]/page');
    const Page = PageMod.default;
    // Server component returns a Promise<JSX>
    const element = await Page({
      params: Promise.resolve({ slug: 'raio-x-marco-2026' }),
    });
    const { container } = render(element as React.ReactElement);

    // Visual nav
    const nav = container.querySelector('nav[aria-label="Breadcrumb"]');
    expect(nav).not.toBeNull();
    const items = nav!.querySelectorAll('li');
    expect(items.length).toBe(3);
    // current page tem aria-current
    expect(nav!.querySelector('[aria-current="page"]')).not.toBeNull();

    // JSON-LD BreadcrumbList
    const scripts = Array.from(
      container.querySelectorAll('script[type="application/ld+json"]'),
    );
    const breadcrumbScript = scripts.find((s) =>
      (s.textContent || '').includes('"@type":"BreadcrumbList"'),
    );
    expect(breadcrumbScript).toBeDefined();
    const parsed = JSON.parse(breadcrumbScript!.textContent || '{}');
    expect(parsed['@type']).toBe('BreadcrumbList');
    expect(parsed.itemListElement).toHaveLength(3);
    expect(parsed.itemListElement[0].name).toBe('Home');
    expect(parsed.itemListElement[0].item).toBe('https://smartlic.tech/');
    expect(parsed.itemListElement[1].name).toBe('Observatório');
    expect(parsed.itemListElement[1].item).toBe(
      'https://smartlic.tech/observatorio',
    );
    expect(parsed.itemListElement[2].item).toBe(
      'https://smartlic.tech/observatorio/raio-x-marco-2026',
    );
    expect(parsed.itemListElement[2].position).toBe(3);
  });
});
