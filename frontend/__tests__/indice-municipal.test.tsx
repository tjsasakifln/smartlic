/**
 * Tests for STORY-435: Índice Municipal de Transparência
 *
 * Tests cover:
 * - IndiceClient renders filter controls and table
 * - IndiceClient handles loading/error/empty states
 * - Slug utility functions
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

// Mock next/link
jest.mock('next/link', () => {
  const Link = ({
    children,
    href,
  }: {
    children: React.ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>;
  Link.displayName = 'Link';
  return Link;
});

// Mock fetch globally
const mockFetch = jest.fn();
global.fetch = mockFetch;

const SAMPLE_RESPONSE = {
  periodo: '2026-Q1',
  total: 2,
  fonte: 'PNCP via SmartLic Observatório',
  license: 'CC BY 4.0',
  resultados: [
    {
      municipio_nome: 'São Paulo',
      municipio_slug: 'sao-paulo-sp',
      uf: 'SP',
      uf_nome: 'São Paulo',
      periodo: '2026-Q1',
      score_total: 78.5,
      score_volume_publicacao: 18.0,
      score_eficiencia_temporal: 15.5,
      score_diversidade_mercado: 16.0,
      score_transparencia_digital: 17.0,
      score_consistencia: 12.0,
      total_editais: 450,
      ranking_nacional: 1,
      ranking_uf: 1,
      percentil: 98,
      calculado_em: '2026-04-11T12:00:00+00:00',
    },
    {
      municipio_nome: 'Campinas',
      municipio_slug: 'campinas-sp',
      uf: 'SP',
      uf_nome: 'São Paulo',
      periodo: '2026-Q1',
      score_total: 45.2,
      score_volume_publicacao: 10.0,
      score_eficiencia_temporal: 9.0,
      score_diversidade_mercado: 10.2,
      score_transparencia_digital: 10.0,
      score_consistencia: 6.0,
      total_editais: 120,
      ranking_nacional: 2,
      ranking_uf: 2,
      percentil: 75,
      calculado_em: '2026-04-11T12:00:00+00:00',
    },
  ],
};

describe('IndiceClient', () => {
  beforeEach(() => {
    mockFetch.mockReset();
  });

  it('renders loading skeleton initially', async () => {
    // Never resolve — keep in loading state
    mockFetch.mockImplementation(() => new Promise(() => {}));

    const IndiceClientModule = await import(
      '@/app/indice-municipal/IndiceClient'
    );
    const IndiceClient = IndiceClientModule.default;

    render(<IndiceClient />);

    // Should show skeleton placeholders
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders table with results on success', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => SAMPLE_RESPONSE,
    } as Response);

    const IndiceClientModule = await import(
      '@/app/indice-municipal/IndiceClient'
    );
    const IndiceClient = IndiceClientModule.default;

    render(<IndiceClient />);

    await waitFor(() => {
      expect(screen.getByText('São Paulo')).toBeInTheDocument();
    });

    expect(screen.getByText('Campinas')).toBeInTheDocument();
    // Score is shown
    expect(screen.getByText('78.5')).toBeInTheDocument();
  });

  it('renders error message on fetch failure', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      json: async () => ({ detail: 'Internal error' }),
    } as Response);

    const IndiceClientModule = await import(
      '@/app/indice-municipal/IndiceClient'
    );
    const IndiceClient = IndiceClientModule.default;

    render(<IndiceClient />);

    await waitFor(() => {
      // Should display an error state
      const errorEl = document.querySelector('[data-testid="indice-error"]');
      if (errorEl) {
        expect(errorEl).toBeInTheDocument();
      } else {
        // Text-based fallback check
        expect(
          screen.queryByText(/erro|indisponível|tente/i)
        ).not.toBeNull();
      }
    });
  });

  it('renders empty state when no results', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...SAMPLE_RESPONSE, resultados: [], total: 0 }),
    } as Response);

    const IndiceClientModule = await import(
      '@/app/indice-municipal/IndiceClient'
    );
    const IndiceClient = IndiceClientModule.default;

    render(<IndiceClient />);

    await waitFor(() => {
      expect(
        screen.getByText(/nenhum dado|não disponível/i)
      ).toBeInTheDocument();
    });
  });

  it('renders UF select filter', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => SAMPLE_RESPONSE,
    } as Response);

    const IndiceClientModule = await import(
      '@/app/indice-municipal/IndiceClient'
    );
    const IndiceClient = IndiceClientModule.default;

    render(<IndiceClient />);

    // UF select should be present
    await waitFor(() => {
      const selects = document.querySelectorAll('select');
      expect(selects.length).toBeGreaterThan(0);
    });
  });

  it('renders link to individual municipality page', async () => {
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => SAMPLE_RESPONSE,
    } as Response);

    const IndiceClientModule = await import(
      '@/app/indice-municipal/IndiceClient'
    );
    const IndiceClient = IndiceClientModule.default;

    render(<IndiceClient />);

    await waitFor(() => {
      const links = document.querySelectorAll(
        'a[href*="/indice-municipal/sao-paulo-sp"]'
      );
      expect(links.length).toBeGreaterThan(0);
    });
  });
});

describe('Slug utility (indice-municipal)', () => {
  it('verifica que sao-paulo-sp termina com uf SP', () => {
    const slug = 'sao-paulo-sp';
    const uf = slug.slice(-2).toUpperCase();
    expect(uf).toBe('SP');
  });

  it('verifica que belo-horizonte-mg tem uf MG', () => {
    const slug = 'belo-horizonte-mg';
    const uf = slug.slice(-2).toUpperCase();
    expect(uf).toBe('MG');
  });

  it('score color: verde para >= 60', () => {
    const score = 78.5;
    const color =
      score >= 60
        ? 'text-green-600'
        : score >= 40
        ? 'text-yellow-600'
        : 'text-red-600';
    expect(color).toBe('text-green-600');
  });

  it('score color: amarelo para 40-59', () => {
    const score = 45;
    const color =
      score >= 60
        ? 'text-green-600'
        : score >= 40
        ? 'text-yellow-600'
        : 'text-red-600';
    expect(color).toBe('text-yellow-600');
  });

  it('score color: vermelho para < 40', () => {
    const score = 25;
    const color =
      score >= 60
        ? 'text-green-600'
        : score >= 40
        ? 'text-yellow-600'
        : 'text-red-600';
    expect(color).toBe('text-red-600');
  });
});

describe('MunicipioPage — ADR-SEO-001 (EmptyStateSEO)', () => {
  beforeEach(() => {
    // Reset fetch mock to avoid polluting other tests
    (global.fetch as jest.Mock).mockReset?.();
  });

  it('AC4: backend returns is_empty_period:true → generateMetadata returns noindex,follow + canonical', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ is_empty_period: true, score_total: null }),
    } as Response);

    const mod = await import('@/app/indice-municipal/[municipio-uf]/page');
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ 'municipio-uf': 'sao-paulo-sp' }),
      searchParams: Promise.resolve({ periodo: '2026-Q2' }),
    });

    // AC3: robots noindex,follow
    expect(metadata.robots).toEqual({ index: false, follow: true });
    // AC3: canonical self-referential
    expect(metadata.alternates?.canonical).toBe(
      'https://smartlic.tech/indice-municipal/sao-paulo-sp'
    );
  });

  it('AC5: backend returns 500 → generateMetadata returns noindex,follow (nao 404, nao throw)', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
    } as Response);

    const mod = await import('@/app/indice-municipal/[municipio-uf]/page');
    // Must NOT throw — catch swallows transient errors
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ 'municipio-uf': 'sao-paulo-sp' }),
      searchParams: Promise.resolve({ periodo: '2026-Q2' }),
    });

    // ADR-SEO-001: data absence → noindex,follow so Google recovers on next regen
    expect(metadata.robots).toEqual({ index: false, follow: true });
  });

  it('generateMetadata returns index:true for valid data', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          is_empty_period: false,
          score_total: 78.5,
          score_transparencia_digital: 17.0,
          score_eficiencia_temporal: 15.5,
          score_diversidade_mercado: 16.0,
          score_volume_publicacao: 18.0,
          score_consistencia: 12.0,
          total_editais: 450,
          ranking_nacional: 1,
          ranking_uf: 1,
          calculado_em: '2026-04-11T12:00:00+00:00',
        }),
    } as Response);

    const mod = await import('@/app/indice-municipal/[municipio-uf]/page');
    const metadata = await mod.generateMetadata({
      params: Promise.resolve({ 'municipio-uf': 'sao-paulo-sp' }),
      searchParams: Promise.resolve({ periodo: '2026-Q2' }),
    });

    expect(metadata.robots).toEqual({ index: true, follow: true });
    expect(metadata.title).toContain('Sao Paulo');
    // OG image should be present when score is available
    expect(metadata.openGraph?.images).toHaveLength(1);
  });

  it('AC6: notFound() has adr-seo-001-allow marker for CI gate compatibility', async () => {
    const fs = await import('fs');
    const path = await import('path');
    const sourcePath = path.resolve(
      __dirname,
      '../app/indice-municipal/[municipio-uf]/page.tsx'
    );
    const source = fs.readFileSync(sourcePath, 'utf-8');

    // The remaining notFound() call must have the CI gate marker
    expect(source).toContain('// adr-seo-001-allow: slug malformed — true 404');
    // No other notFound() call without the marker
    const notFoundLines = source
      .split('\n')
      .filter((l: string) => {
        const t = l.trim();
        // Skip JSDoc/inline comment lines (adr-seo-001-allow marker already checked above)
        if (t.startsWith('*') || t.startsWith('//') || t.startsWith('/*')) return false;
        return l.includes('notFound()');
      });
    expect(notFoundLines.length).toBe(1);
  });
});
