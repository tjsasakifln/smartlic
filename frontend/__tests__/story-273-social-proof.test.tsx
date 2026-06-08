/**
 * CONV-010-3 (#1510): Homepage refatorada como terminal de inteligência.
 *
 * Substitui STORY-273 + REPO-COMMS #1289 — a homepage antiga tinha 7 seções
 * estáticas; a nova é um "terminal de inteligência" com busca + 6 intent cards.
 *
 * Tests:
 * - Estrutura: search bar acima da dobra, 6 intent cards
 * - LGPD badge em português no Footer (mantido da STORY-273)
 */

import { render, screen } from '@testing-library/react';
import React from 'react';

// ---- Mocks ----

// Mock framer-motion
jest.mock('framer-motion', () => {
  const React = require('react');
  const motion = new Proxy(
    {},
    {
      get: (_target: unknown, prop: string) =>
        React.forwardRef(
          (
            { children, ...props }: { children?: React.ReactNode; [key: string]: unknown },
            ref: React.Ref<HTMLElement>
          ) => {
            const safe: Record<string, unknown> = {};
            for (const [k, v] of Object.entries(props)) {
              if (typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean') {
                safe[k] = v;
              }
            }
            return React.createElement(prop, { ...safe, ref }, children);
          }
        ),
    }
  );
  return { motion, AnimatePresence: ({ children }: { children: React.ReactNode }) => children };
});

// Mock IntentRouter hook (CONV-007-2, #1511)
jest.mock('../app/components/conversion/IntentRouter', () => ({
  useIntentDetection: () => ({ cluster: 'geral' as const, source: 'fallback' as const }),
  detectIntentFromSearchTerm: () => 'geral',
  detectIntentFromReferrer: () => null,
}));

// Mock Footer
jest.mock('../app/components/Footer', () => {
  return function MockFooter() {
    return <footer data-testid="footer">Footer</footer>;
  };
});

// Mock HomeFaqStructuredData
jest.mock('../app/components/HomeFaqStructuredData', () => ({
  HomeFaqStructuredData: function MockHomeFaqStructuredData() {
    return null;
  },
}));

// Mock ExitIntentPopup
jest.mock('../app/components/ExitIntentPopup', () => ({
  ExitIntentPopup: function MockExitIntentPopup() {
    return null;
  },
}));

// ---- Import ----

import LandingPage from '../app/page';

// ---- Tests ----

describe('CONV-010-3 (#1510): Homepage — Terminal de Inteligência', () => {
  beforeEach(() => {
    render(<LandingPage />);
  });

  describe('Estrutura principal', () => {
    it('renderiza a search bar acima da dobra', () => {
      expect(screen.getByPlaceholderText(/Busque editais/i)).toBeInTheDocument();
    });

    it('renderiza o seletor de setor', () => {
      expect(screen.getByRole('combobox', { name: /setor/i })).toBeInTheDocument();
    });

    it('renderiza o botão Buscar', () => {
      expect(screen.getByRole('button', { name: /Buscar/i })).toBeInTheDocument();
    });
  });

  describe('Intent Cards (6)', () => {
    const expectedCards = [
      'Quero vender para o governo',
      'Quero pesquisar um concorrente',
      'Quero encontrar parceiros',
      'Quero entender meu mercado',
      'Quero acompanhar editais',
      'Quero me preparar para licitar',
    ];

    it('renderiza exatamente 6 intent cards', () => {
      const cards = screen.getAllByRole('article');
      expect(cards).toHaveLength(6);
    });

    for (const title of expectedCards) {
      it(`renderiza o card "${title}"`, () => {
        expect(screen.getByText(title)).toBeInTheDocument();
      });
    }

    it('cada card tem um link "Saiba mais"', () => {
      const links = screen.getAllByText(/Saiba mais/);
      expect(links).toHaveLength(6);
    });
  });

  describe('Seções removidas (intencionalmente)', () => {
    const removedIds = [
      'hero-b2g',
      'antecipe-decida-execute',
      'terminal-comparison',
      'social-proof-metrics',
      'personas-section',
      'pricing-b2g',
      'market-social-proof',
      'newsletter-footer',
      'b2g-intel-theme',
      'beta-counter',
    ];

    for (const testId of removedIds) {
      it(`NÃO renderiza a seção antiga "${testId}"`, () => {
        expect(screen.queryByTestId(testId)).not.toBeInTheDocument();
      });
    }
  });

  describe('Footer (mantido)', () => {
    it('renderiza o footer', () => {
      expect(screen.getByTestId('footer')).toBeInTheDocument();
    });
  });
});

// ---- AC5: LGPD Badge Test (Footer) ----

describe('CONV-010-3: LGPD Badge em Português (mantido da STORY-273)', () => {
  beforeEach(() => {
    jest.resetModules();
  });

  it('deve exibir o selo LGPD em português no Footer', async () => {
    jest.unmock('../app/components/Footer');

    // Mock FooterNewsletterForm
    jest.mock('../app/components/FooterNewsletterForm', () => ({
      FooterNewsletterForm: function MockFooterNewsletterForm() {
        return <div data-testid="newsletter-form">Newsletter</div>;
      },
    }));

    // Mock dependencies for real Footer rendering
    jest.mock('../lib/copy/valueProps', () => ({
      footer: {
        dataSource: 'Dados de fontes oficiais',
        disclaimer: 'Plataforma independente',
        trustBadge: 'Dados verificados',
      },
    }));

    jest.mock('../app/components/BackendStatusIndicator', () => ({
      useBackendStatusContext: () => ({ status: 'online' as const }),
    }));

    const { default: Footer } = await import('../app/components/Footer');

    render(React.createElement(Footer));

    expect(screen.getByText('Em conformidade com a LGPD')).toBeInTheDocument();
    expect(screen.queryByText('LGPD Compliant')).not.toBeInTheDocument();
  });
});
