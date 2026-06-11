/**
 * Tests for AutonomousLandingShell component — CONV-010-2 (#1509)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import AutonomousLandingShell from '../app/components/conversion/AutonomousLandingShell';
import type { EntityType } from '../app/components/conversion/AutonomousLandingShell';

// Mock framer-motion to avoid animation issues in tests.
// Strips framer-motion-specific props that React doesn't recognize on DOM elements.
const MOTION_PROPS = new Set([
  'variants', 'initial', 'animate', 'exit', 'whileInView',
  'whileHover', 'whileTap', 'whileFocus', 'whileDrag',
  'viewport', 'transition', 'layout', 'layoutId',
]);
function stripMotionProps(props: Record<string, unknown>): Record<string, unknown> {
  const clean: Record<string, unknown> = {};
  for (const key of Object.keys(props)) {
    if (!MOTION_PROPS.has(key)) clean[key] = props[key];
  }
  return clean;
}
jest.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) =>
      React.createElement('div', stripMotionProps(props as Record<string, unknown>), children),
  },
  AnimatePresence: ({ children }: React.PropsWithChildren<Record<string, unknown>>) =>
    React.createElement(React.Fragment, null, children),
}));

describe('AutonomousLandingShell', () => {
  const baseProps = {
    entityType: 'fornecedor' as EntityType,
    entityName: 'Empresa Exemplo Ltda',
    entityData: { total_contratos: 42 },
    valueProp: 'Análise concorrencial com IA',
    insights: [
      { label: 'Contratos', value: '42', icon: 'chart' as const },
      { label: 'Estados', value: '5', icon: 'building' as const },
    ],
    ctaVariant: 'trial' as const,
  };

  beforeEach(() => {
    // Mock mixpanel
    Object.defineProperty(window, 'mixpanel', {
      value: { track: jest.fn() },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('renders ValuePropositionAboveFold with correct entity name and value prop', () => {
    render(<AutonomousLandingShell {...baseProps} />);

    expect(
      screen.getByText('Quer vencer mais licitações como Empresa Exemplo Ltda?'),
    ).toBeInTheDocument();
    expect(screen.getByText('Análise concorrencial com IA')).toBeInTheDocument();
  });

  it('renders AhaMomentPanel with insights', () => {
    render(<AutonomousLandingShell {...baseProps} />);

    expect(screen.getByText('Contratos')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
    expect(screen.getByText('Estados')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
  });

  it('renders CTAContextual with correct variant', () => {
    render(<AutonomousLandingShell {...baseProps} />);

    const ctaLink = screen.getByTestId('cta-contextual');
    expect(ctaLink).toBeInTheDocument();
    expect(ctaLink).toHaveTextContent(/Testar grátis/);
  });

  it('fires Mixpanel event on mount', () => {
    const trackSpy = jest.fn();
    Object.defineProperty(window, 'mixpanel', {
      value: { track: trackSpy },
      writable: true,
      configurable: true,
    });

    render(<AutonomousLandingShell {...baseProps} />);

    expect(trackSpy).toHaveBeenCalledWith('landing_autonomous_view', {
      entityType: 'fornecedor',
      entityName: 'Empresa Exemplo Ltda',
    });
  });

  it('renders supporting detail when provided', () => {
    render(
      <AutonomousLandingShell
        {...baseProps}
        supportingDetail="Suporte adicional para sua análise"
      />,
    );

    expect(
      screen.getByText('Suporte adicional para sua análise'),
    ).toBeInTheDocument();
  });

  it('renders CTA text override when provided', () => {
    render(
      <AutonomousLandingShell
        {...baseProps}
        ctaText="Comprar agora"
      />,
    );

    const ctaLink = screen.getByTestId('cta-contextual');
    expect(ctaLink).toHaveTextContent('Comprar agora');
  });

  it('renders correctly for different entity types', () => {
    const entityTypes: Array<{
      type: EntityType;
      name: string;
      headline: string;
    }> = [
      { type: 'orgao', name: 'Prefeitura de SP', headline: 'Quer vender para Prefeitura de SP?' },
      { type: 'setor', name: 'TI', headline: 'Oportunidades no setor — TI' },
      { type: 'municipio', name: 'São Paulo', headline: 'Licitações em São Paulo — acompanhe em tempo real' },
      { type: 'contrato', name: 'Contrato ABC', headline: 'Análise completa do contrato — Contrato ABC' },
    ];

    entityTypes.forEach(({ type, name, headline }) => {
      const { unmount } = render(
        <AutonomousLandingShell
          entityType={type}
          entityName={name}
          entityData={{}}
          valueProp={`Valor para ${type}`}
          insights={[{ label: 'Item', value: '1', icon: 'target' }]}
          ctaVariant="search"
        />,
      );

      expect(screen.getByText(headline)).toBeInTheDocument();
      unmount();
    });
  });

  it('renders main element with accessible aria-label', () => {
    render(<AutonomousLandingShell {...baseProps} />);

    const main = screen.getByRole('main');
    expect(main).toBeInTheDocument();
    expect(main).toHaveAttribute(
      'aria-label',
      'Página autônoma — Empresa Exemplo Ltda',
    );
  });
});
