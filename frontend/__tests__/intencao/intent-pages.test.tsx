/**
 * Tests for 4 intent cluster landing pages — CONV-007-2 / #1316, #1401
 *
 * Covers:
 * - Each page renders its specific headline
 * - Each page renders primary and secondary CTAs
 * - Each page renders step titles and descriptions
 * - Mobile responsiveness (CSS classes)
 * - JSON-LD structured data presence
 */
// Mock AuthProvider before any imports (required by LandingNavbar -> NavbarAuthCTA)
jest.mock('../../app/components/AuthProvider', () => {
  const React = require('react');
  return {
    useAuth: () => ({ user: null, session: null, loading: false }),
    AuthProvider: ({ children }: { children: React.ReactNode }) =>
      React.createElement(React.Fragment, null, children),
  };
});

import React from 'react';
import { render, screen } from '@testing-library/react';
import ComercialPage from '../../app/intencao/comercial/page';
import InvestigativaPage from '../../app/intencao/investigativa/page';
import JuridicaPage from '../../app/intencao/juridica/page';
import SubcontratacaoPage from '../../app/intencao/subcontratacao/page';

describe('ComercialPage', () => {
  it('renders the headline', () => {
    render(<ComercialPage />);
    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /venda para o governo com inteligência/i,
      }),
    ).toBeInTheDocument();
  });

  it('renders primary CTA in both hero and final section', () => {
    render(<ComercialPage />);
    const ctas = screen.getAllByRole('link', {
      name: /relatório de fornecedor.*r\$67/i,
    });
    expect(ctas.length).toBe(2);
    ctas.forEach((cta) => {
      expect(cta).toHaveAttribute('href', '/checkout?sku=relatorio-fornecedor');
    });
  });

  it('renders secondary CTA', () => {
    render(<ComercialPage />);
    const ctas = screen.getAllByRole('link', {
      name: /monitoramento de editais/i,
    });
    expect(ctas.length).toBe(2);
    ctas.forEach((cta) => {
      expect(cta).toHaveAttribute('href', '/signup?source=intent-comercial');
    });
  });

  it('renders 3 step titles with data points', () => {
    render(<ComercialPage />);
    expect(
      screen.getByText('2 milhões de contratos monitorados'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('27 estados com cobertura nacional'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('15+ setores classificados por IA'),
    ).toBeInTheDocument();
  });

  it('includes JSON-LD structured data', () => {
    render(<ComercialPage />);
    const scripts = document.querySelectorAll(
      'script[type="application/ld+json"]',
    );
    expect(scripts.length).toBeGreaterThan(0);
  });
});

describe('InvestigativaPage', () => {
  it('renders the headline', () => {
    render(<InvestigativaPage />);
    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /pesquise licitações com profundidade/i,
      }),
    ).toBeInTheDocument();
  });

  it('renders primary CTA', () => {
    render(<InvestigativaPage />);
    const ctas = screen.getAllByRole('link', {
      name: /mapa de oportunidades.*r\$47/i,
    });
    expect(ctas.length).toBe(2);
    ctas.forEach((cta) => {
      expect(cta).toHaveAttribute('href', '/checkout?sku=mapa-oportunidades');
    });
  });

  it('renders secondary CTA', () => {
    render(<InvestigativaPage />);
    const ctas = screen.getAllByRole('link', {
      name: /relatório setorial/i,
    });
    expect(ctas.length).toBe(2);
    ctas.forEach((cta) => {
      expect(cta).toHaveAttribute('href', '/checkout?sku=relatorio-setorial');
    });
  });

  it('renders 3 step titles with data points', () => {
    render(<InvestigativaPage />);
    expect(
      screen.getByText('50 mil+ órgãos públicos mapeados'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('R$ 1 bilhão+ em contratos analisados'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Relatórios setoriais completos'),
    ).toBeInTheDocument();
  });

  it('includes JSON-LD structured data', () => {
    render(<InvestigativaPage />);
    const scripts = document.querySelectorAll(
      'script[type="application/ld+json"]',
    );
    expect(scripts.length).toBeGreaterThan(0);
  });
});

describe('JuridicaPage', () => {
  it('renders the headline', () => {
    render(<JuridicaPage />);
    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /fundamentação jurídica para licitações/i,
      }),
    ).toBeInTheDocument();
  });

  it('renders primary CTA (lead capture)', () => {
    render(<JuridicaPage />);
    const ctas = screen.getAllByRole('link', {
      name: /diagnóstico gratuito/i,
    });
    expect(ctas.length).toBe(2);
    ctas.forEach((cta) => {
      expect(cta).toHaveAttribute('href', '/signup?source=intent-juridica');
    });
  });

  it('renders secondary CTA (consultoria)', () => {
    render(<JuridicaPage />);
    const ctas = screen.getAllByRole('link', {
      name: /falar com consultoria/i,
    });
    expect(ctas.length).toBe(2);
    ctas.forEach((cta) => {
      expect(cta).toHaveAttribute('href', '/contato');
    });
  });

  it('renders 3 step titles with data points', () => {
    render(<JuridicaPage />);
    expect(
      screen.getByText('100% da legislação federal disponível'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Editais completos com análise jurídica'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Diagnóstico personalizado gratuito'),
    ).toBeInTheDocument();
  });

  it('includes JSON-LD structured data', () => {
    render(<JuridicaPage />);
    const scripts = document.querySelectorAll(
      'script[type="application/ld+json"]',
    );
    expect(scripts.length).toBeGreaterThan(0);
  });
});

describe('SubcontratacaoPage', () => {
  it('renders the headline', () => {
    render(<SubcontratacaoPage />);
    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /encontre parceiros de licitação/i,
      }),
    ).toBeInTheDocument();
  });

  it('renders primary CTA', () => {
    render(<SubcontratacaoPage />);
    const ctas = screen.getAllByRole('link', {
      name: /matching.*relatório.*r\$97/i,
    });
    expect(ctas.length).toBe(2);
    ctas.forEach((cta) => {
      expect(cta).toHaveAttribute(
        'href',
        '/checkout?sku=relatorio-subcontratacao',
      );
    });
  });

  it('renders secondary CTA', () => {
    render(<SubcontratacaoPage />);
    const ctas = screen.getAllByRole('link', {
      name: /ver editais recentes/i,
    });
    expect(ctas.length).toBe(2);
    ctas.forEach((cta) => {
      expect(cta).toHaveAttribute('href', '/licitacoes');
    });
  });

  it('renders 3 step titles with data points', () => {
    render(<SubcontratacaoPage />);
    expect(
      screen.getByText('5 mil+ empresas parceiras cadastradas'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('27 estados com oportunidades'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Match inteligente com vencedores'),
    ).toBeInTheDocument();
  });

  it('includes JSON-LD structured data', () => {
    render(<SubcontratacaoPage />);
    const scripts = document.querySelectorAll(
      'script[type="application/ld+json"]',
    );
    expect(scripts.length).toBeGreaterThan(0);
  });
});

describe('Shared layout patterns', () => {
  it.each([
    ['Comercial', ComercialPage],
    ['Investigativa', InvestigativaPage],
    ['Juridica', JuridicaPage],
    ['Subcontratacao', SubcontratacaoPage],
  ])('%s page has responsive hero layout', (_name, PageComponent) => {
    const { container } = render(<PageComponent />);
    const ctaContainers = container.querySelectorAll('.flex.flex-col');
    expect(ctaContainers.length).toBeGreaterThan(0);
  });

  it.each([
    ['Comercial', ComercialPage],
    ['Investigativa', InvestigativaPage],
    ['Juridica', JuridicaPage],
    ['Subcontratacao', SubcontratacaoPage],
  ])('%s page uses semantic main element', (_name, PageComponent) => {
    const { container } = render(<PageComponent />);
    const main = container.querySelector('main');
    expect(main).not.toBeNull();
  });

  it.each([
    ['Comercial', ComercialPage],
    ['Investigativa', InvestigativaPage],
    ['Juridica', JuridicaPage],
    ['Subcontratacao', SubcontratacaoPage],
  ])('%s page renders "Como funciona" section', (_name, PageComponent) => {
    render(<PageComponent />);
    expect(
      screen.getByRole('heading', { level: 2, name: /como funciona/i }),
    ).toBeInTheDocument();
  });
});
