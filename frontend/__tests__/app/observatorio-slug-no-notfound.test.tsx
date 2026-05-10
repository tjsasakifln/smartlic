/**
 * Issue #1034 (HOTFIX): /observatorio/[slug] must NOT call `notFound()` for
 * null/empty backend payloads under ISR — that turns a transient blip into
 * a 24h hard 404. This test pins the new behavior:
 *
 * - Transient failure (5xx / network throw) → fetchRelatorio re-throws so ISR
 *   keeps the last-good cache. `notFound()` is NOT called.
 * - Empty period (`is_empty_period:true`, total_editais: 0) → page renders
 *   <EmptyStateSEO> + generateMetadata sets `robots.index=false, follow=true`.
 *   `notFound()` is NOT called.
 * - Malformed slug → `notFound()` IS called (preserved 404 behavior).
 */

import { render } from '@testing-library/react';
import React from 'react';

const mockNotFound = jest.fn(() => {
  // Mimic next/navigation's notFound() control-flow throw so we can detect
  // whether the page invoked it.
  const err = new Error('NEXT_NOT_FOUND');
  (err as any).digest = 'NEXT_NOT_FOUND';
  throw err;
});

jest.mock('next/navigation', () => ({
  notFound: mockNotFound,
}));

jest.mock('@/app/observatorio/[slug]/ObservatorioRelatorioClient', () => {
  const Mock = () => <div data-testid="observatorio-client" />;
  Mock.displayName = 'ObservatorioRelatorioClientMock';
  return { __esModule: true, default: Mock };
});

jest.mock('@sentry/nextjs', () => ({
  captureMessage: jest.fn(),
}));

const fullRelatorio = {
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

const emptyPeriodRelatorio = {
  ...fullRelatorio,
  total_editais: 0,
  is_empty_period: true,
  periodo: '',
  top_ufs: [],
  modalidades: [],
  tendencia_semanal: [],
  setores_em_alta: [],
};

global.fetch = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Page render — no notFound() for null/empty payloads (Issue #1034)
// ---------------------------------------------------------------------------

describe('RelatorioPage — Issue #1034 ban notFound() for null/empty payloads', () => {
  it('payload com total_editais: 0 (is_empty_period) renderiza EmptyStateSEO e NÃO chama notFound()', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => emptyPeriodRelatorio,
    });
    const PageMod = await import('@/app/observatorio/[slug]/page');
    const Page = PageMod.default;
    const element = await Page({
      params: Promise.resolve({ slug: 'raio-x-marco-2026' }),
    });
    const { container, getByTestId } = render(element as React.ReactElement);

    // notFound() NUNCA é chamado para empty period.
    expect(mockNotFound).not.toHaveBeenCalled();
    // EmptyStateSEO renderizado.
    expect(getByTestId('empty-state-seo')).toBeTruthy();
    // h1 contém o display do mês/ano.
    const h1 = container.querySelector('h1');
    expect(h1?.textContent).toContain('Março');
    expect(h1?.textContent).toContain('2026');
  });

  it('backend retorna 4xx (resp.ok=false, status<500) → renderiza EmptyStateSEO e NÃO chama notFound()', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({}),
    });
    const PageMod = await import('@/app/observatorio/[slug]/page');
    const Page = PageMod.default;
    const element = await Page({
      params: Promise.resolve({ slug: 'raio-x-abril-2026' }),
    });
    const { getByTestId } = render(element as React.ReactElement);
    expect(mockNotFound).not.toHaveBeenCalled();
    expect(getByTestId('empty-state-seo')).toBeTruthy();
  });

  it('falha transitória (5xx) → fetchRelatorio THROWS para preservar last-good ISR; notFound() NÃO é chamado', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({ error: 'service_unavailable' }),
    });
    const PageMod = await import('@/app/observatorio/[slug]/page');
    const Page = PageMod.default;

    let thrown: unknown = null;
    try {
      await Page({ params: Promise.resolve({ slug: 'raio-x-marco-2026' }) });
    } catch (e) {
      thrown = e;
    }

    // Page deve propagar erro (não chamar notFound() — ISR mantém cache antigo).
    expect(thrown).not.toBeNull();
    // Erro NÃO é o NEXT_NOT_FOUND digest.
    expect(mockNotFound).not.toHaveBeenCalled();
  });

  it('falha de rede (fetch rejeita) → bubble up; notFound() NÃO é chamado', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('ECONNRESET'));
    const PageMod = await import('@/app/observatorio/[slug]/page');
    const Page = PageMod.default;

    let thrown: unknown = null;
    try {
      await Page({ params: Promise.resolve({ slug: 'raio-x-marco-2026' }) });
    } catch (e) {
      thrown = e;
    }
    expect(thrown).not.toBeNull();
    expect(mockNotFound).not.toHaveBeenCalled();
  });

  it('slug malformado → notFound() AINDA é chamado (preserva 404 para slug inválido)', async () => {
    const PageMod = await import('@/app/observatorio/[slug]/page');
    const Page = PageMod.default;

    let thrown: unknown = null;
    try {
      await Page({ params: Promise.resolve({ slug: 'slug-invalido' }) });
    } catch (e) {
      thrown = e;
    }
    // notFound() é invocado para slug malformado (preserva 404 behavior).
    expect(mockNotFound).toHaveBeenCalledTimes(1);
    // E sua exceção sobe para o caller.
    expect(thrown).not.toBeNull();
  });

  it('payload com dados reais ainda renderiza o relatório completo (não regression)', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => fullRelatorio,
    });
    const PageMod = await import('@/app/observatorio/[slug]/page');
    const Page = PageMod.default;
    const element = await Page({
      params: Promise.resolve({ slug: 'raio-x-marco-2026' }),
    });
    const { getByTestId, queryByTestId } = render(element as React.ReactElement);

    expect(mockNotFound).not.toHaveBeenCalled();
    expect(getByTestId('observatorio-client')).toBeTruthy();
    expect(queryByTestId('empty-state-seo')).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// generateMetadata — robots:noindex,follow para empty/null (Issue #1034)
// ---------------------------------------------------------------------------

describe('generateMetadata — Issue #1034 robots noindex,follow para empty/null', () => {
  it('total_editais: 0 → robots.index=false, robots.follow=true', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => emptyPeriodRelatorio,
    });
    const { generateMetadata } = await import('@/app/observatorio/[slug]/page');
    const meta = await generateMetadata({
      params: Promise.resolve({ slug: 'raio-x-marco-2026' }),
    });
    const robots = meta.robots as { index?: boolean; follow?: boolean } | undefined;
    expect(robots?.index).toBe(false);
    expect(robots?.follow).toBe(true);
  });

  it('5xx transitório → metadata não crasha; robots.index=false', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 503,
      json: async () => ({}),
    });
    const { generateMetadata } = await import('@/app/observatorio/[slug]/page');
    const meta = await generateMetadata({
      params: Promise.resolve({ slug: 'raio-x-marco-2026' }),
    });
    const robots = meta.robots as { index?: boolean; follow?: boolean } | undefined;
    expect(robots?.index).toBe(false);
    expect(robots?.follow).toBe(true);
  });
});
