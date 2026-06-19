/**
 * Issue #2043 (P0-2): analise/[hash] substituir notFound() por EmptyStateSEO.
 *
 * Contexto: ISR cacheia 404 → Google desindexa URL. Viola ADR-SEO-001.
 *
 * ACs:
 * - AC4: Backend retorna 404 → página renderiza EmptyStateSEO (HTTP 200)
 * - AC5: Backend retorna 500 → página renderiza EmptyStateSEO (não throw, não 404)
 */

import { render } from '@testing-library/react';
import React from 'react';

const mockNotFound = jest.fn(() => {
  const err = new Error('NEXT_NOT_FOUND');
  (err as unknown as { digest: string }).digest = 'NEXT_NOT_FOUND';
  throw err;
});

jest.mock('next/navigation', () => ({
  notFound: mockNotFound,
}));

jest.mock('@/app/analise/[hash]/AnalysisViewTracker', () => ({
  AnalysisViewTracker: () => <div data-testid="view-tracker" />,
}));

jest.mock('@/components/share/ShareButtons', () => ({
  __esModule: true,
  default: () => <div data-testid="share-buttons" />,
}));

jest.mock('@/components/blog/SchemaMarkup', () => ({
  __esModule: true,
  default: () => <div data-testid="schema-markup" />,
}));

const mockAnalysisPayload = {
  hash: 'abc123def456',
  bid_id: 'bid-001',
  bid_title: 'Pregão Eletrônico - Material Hospitalar',
  bid_orgao: 'Secretaria de Saúde',
  bid_uf: 'SP',
  bid_valor: 150000.0,
  bid_modalidade: 'Pregão',
  viability_score: 75,
  viability_level: 'alta',
  viability_factors: {
    modalidade: 80,
    modalidade_label: 'Modalidade adequada',
    timeline: 70,
    timeline_label: 'Prazo razoável',
    value_fit: 75,
    value_fit_label: 'Valor compatível',
    geography: 70,
    geography_label: 'Geograficamente viável',
  },
  view_count: 5,
  created_at: '2026-06-15T10:00:00Z',
};

global.fetch = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
});

describe('AnalisePage — Issue #2043 ban notFound() for null/empty payloads', () => {
  it('AC4: backend retorna 404 → renderiza EmptyStateSEO e NÃO chama notFound()', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({}),
    });

    const PageMod = await import('@/app/analise/[hash]/page');
    const Page = PageMod.default;
    const element = await Page({
      params: Promise.resolve({ hash: 'abc123def456' }),
    });
    const { getByTestId } = render(element as React.ReactElement);

    expect(mockNotFound).not.toHaveBeenCalled();
    expect(getByTestId('empty-state-seo')).toBeTruthy();
  });

  it('AC5: backend retorna 500 → renderiza EmptyStateSEO e NÃO chama notFound()', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    const PageMod = await import('@/app/analise/[hash]/page');
    const Page = PageMod.default;
    const element = await Page({
      params: Promise.resolve({ hash: 'abc123def456' }),
    });
    const { getByTestId } = render(element as React.ReactElement);

    expect(mockNotFound).not.toHaveBeenCalled();
    expect(getByTestId('empty-state-seo')).toBeTruthy();
  });

  it('hash malformado → notFound() AINDA é chamado (preserva 404 para formato inválido)', async () => {
    const PageMod = await import('@/app/analise/[hash]/page');
    const Page = PageMod.default;

    // notFound() throws NEXT_NOT_FOUND — verify it was called.
    // (Jest mock may swallow exception depending on async context.)
    expect.hasAssertions();
    try {
      await Page({ params: Promise.resolve({ hash: 'not-a-valid-hash!!!' }) });
    } catch {
      // Expected — hash format is invalid so notFound() was invoked.
    }
    expect(mockNotFound).toHaveBeenCalledTimes(1);
  });

  it('payload com dados reais renderiza página completa (não regression)', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockAnalysisPayload,
    });

    const PageMod = await import('@/app/analise/[hash]/page');
    const Page = PageMod.default;
    const element = await Page({
      params: Promise.resolve({ hash: 'abc123def456' }),
    });
    const { getByTestId, queryByTestId } = render(element as React.ReactElement);

    expect(mockNotFound).not.toHaveBeenCalled();
    expect(queryByTestId('empty-state-seo')).toBeNull();
    expect(getByTestId('view-tracker')).toBeTruthy();
  });

  it('erro de rede → renderiza EmptyStateSEO e NÃO chama notFound()', async () => {
    (global.fetch as jest.Mock).mockRejectedValue(new Error('ECONNRESET'));

    const PageMod = await import('@/app/analise/[hash]/page');
    const Page = PageMod.default;
    const element = await Page({
      params: Promise.resolve({ hash: 'abc123def456' }),
    });
    const { getByTestId } = render(element as React.ReactElement);

    expect(mockNotFound).not.toHaveBeenCalled();
    expect(getByTestId('empty-state-seo')).toBeTruthy();
  });
});

describe('AnalisePage generateMetadata — robots noindex,follow para null/empty', () => {
  it('backend retorna 404 → generateMetadata retorna robots.index=false', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 404,
      json: async () => ({}),
    });

    const { generateMetadata } = await import('@/app/analise/[hash]/page');
    const meta = await generateMetadata({
      params: Promise.resolve({ hash: 'abc123def456' }),
    });
    const robots = meta.robots as { index?: boolean; follow?: boolean } | undefined;
    expect(robots?.index).toBe(false);
    expect(robots?.follow).toBe(true);
  });

  it('backend retorna 500 → generateMetadata retorna robots.index=false', async () => {
    (global.fetch as jest.Mock).mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });

    const { generateMetadata } = await import('@/app/analise/[hash]/page');
    const meta = await generateMetadata({
      params: Promise.resolve({ hash: 'abc123def456' }),
    });
    const robots = meta.robots as { index?: boolean; follow?: boolean } | undefined;
    expect(robots?.index).toBe(false);
    expect(robots?.follow).toBe(true);
  });
});
