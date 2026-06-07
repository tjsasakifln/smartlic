/**
 * Tests for IntentTrail — CONV-007-2
 *
 * Covers:
 * - Rendering all 5 variants (4 clusters + fallback/geral)
 * - Explicit cluster prop
 * - Individual prop overrides
 * - Auto-detection from search params
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import IntentTrail from '../app/components/conversion/IntentTrail';
import type { IntentCluster } from '../app/components/conversion/IntentRouter';
import { CLUSTER_LABELS } from '../app/components/conversion/intent-keywords';

// ── Mocks ───────────────────────────────────────────────────────────────

const mockUseSearchParams = jest.fn();

jest.mock('next/navigation', () => ({
  useSearchParams: () => mockUseSearchParams(),
}));

beforeEach(() => {
  // Default: no search params
  mockUseSearchParams.mockReturnValue(new URLSearchParams());
});

// ── Tests ───────────────────────────────────────────────────────────────

describe('IntentTrail — explicit clusters', () => {
  const clusters: IntentCluster[] = [
    'comercial',
    'investigativa',
    'juridica',
    'subcontratacao',
    'geral',
  ];

  for (const cluster of clusters) {
    it(`renders correct content for "${cluster}" cluster`, () => {
      render(<IntentTrail cluster={cluster} />);

      // Each cluster has a unique headline and offer — verify they render
      const section = screen.getByLabelText(`Oferta ${CLUSTER_LABELS[cluster]}`);
      expect(section).toBeInTheDocument();

      // CTA should always be present
      expect(screen.getByRole('link', { name: /Começar trial grátis/ })).toBeInTheDocument();
    });
  }

  it('renders comercial-specific headline', () => {
    render(<IntentTrail cluster="comercial" />);
    expect(
      screen.getByText('Venda para o governo com inteligência'),
    ).toBeInTheDocument();
  });

  it('renders investigativa-specific headline', () => {
    render(<IntentTrail cluster="investigativa" />);
    expect(
      screen.getByText('Pesquise licitações com profundidade'),
    ).toBeInTheDocument();
  });

  it('renders juridica-specific headline', () => {
    render(<IntentTrail cluster="juridica" />);
    expect(
      screen.getByText('Fundamentação jurídica para licitações'),
    ).toBeInTheDocument();
  });

  it('renders subcontratacao-specific headline', () => {
    render(<IntentTrail cluster="subcontratacao" />);
    expect(
      screen.getByText('Encontre parceiros de licitação'),
    ).toBeInTheDocument();
  });

  it('renders geral (fallback) headline', () => {
    render(<IntentTrail cluster="geral" />);
    expect(
      screen.getByText('Inteligência em licitações públicas'),
    ).toBeInTheDocument();
  });
});

describe('IntentTrail — props overrides', () => {
  it('overrides headline', () => {
    render(<IntentTrail cluster="comercial" headline="Título customizado" />);
    expect(screen.getByText('Título customizado')).toBeInTheDocument();
    expect(screen.queryByText('Venda para o governo com inteligência')).not.toBeInTheDocument();
  });

  it('overrides offer text', () => {
    render(
      <IntentTrail cluster="investigativa" offer="Oferta personalizada para pesquisa." />,
    );
    expect(screen.getByText('Oferta personalizada para pesquisa.')).toBeInTheDocument();
  });

  it('overrides CTA text', () => {
    render(<IntentTrail cluster="juridica" ctaText="Acessar agora →" />);
    expect(screen.getByRole('link', { name: 'Acessar agora →' })).toBeInTheDocument();
  });

  it('overrides CTA link', () => {
    render(<IntentTrail cluster="subcontratacao" ctaLink="/custom-path" />);
    const link = screen.getByRole('link', { name: /Começar trial grátis/ });
    expect(link).toHaveAttribute('href', '/custom-path');
  });

  it('overrides secondary action', () => {
    render(
      <IntentTrail
        cluster="comercial"
        secondaryAction={{ text: 'Ação secundária', href: '/secondary' }}
      />,
    );
    const secondary = screen.getByRole('link', { name: 'Ação secundária' });
    expect(secondary).toHaveAttribute('href', '/secondary');
  });

  it('renders CTA with correct default signup link per cluster', () => {
    render(<IntentTrail cluster="comercial" />);
    expect(screen.getByRole('link', { name: /Começar trial grátis/ })).toHaveAttribute(
      'href',
      '/signup?source=intent-comercial',
    );
  });
});

describe('IntentTrail — auto-detection via useSearchParams', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('detects cluster from "q" search param', () => {
    mockUseSearchParams.mockReturnValue(new URLSearchParams('q=vender+para+governo'));
    render(<IntentTrail />);
    expect(
      screen.getByText('Venda para o governo com inteligência'),
    ).toBeInTheDocument();
  });

  it('falls back to geral when no intent matches', () => {
    mockUseSearchParams.mockReturnValue(new URLSearchParams('q=receita+federal'));
    render(<IntentTrail />);
    expect(
      screen.getByText('Inteligência em licitações públicas'),
    ).toBeInTheDocument();
  });

  it('uses explicit searchTerm override for detection', () => {
    mockUseSearchParams.mockReturnValue(new URLSearchParams(''));
    render(<IntentTrail searchTerm="impugnação edital" />);
    expect(
      screen.getByText('Fundamentação jurídica para licitações'),
    ).toBeInTheDocument();
  });

  it('explicit cluster prop takes precedence over search params', () => {
    mockUseSearchParams.mockReturnValue(new URLSearchParams('q=vender'));
    render(<IntentTrail cluster="juridica" />);
    // Should show juridica content, not comercial from search params
    expect(
      screen.getByText('Fundamentação jurídica para licitações'),
    ).toBeInTheDocument();
  });
});


