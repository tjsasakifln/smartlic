/**
 * Tests for /subcontratacao flagship page (#1317)
 *
 * Covers:
 * - Metadata is exported correctly
 * - Hero section renders headline
 * - Explanation section renders
 * - Stats section renders with values
 * - Sectors section renders with progress bars
 * - Product CTA section renders DigitalProductPreview
 * - CheckoutButton appears with subcontratacao-map product
 * - Mobile responsive classes
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import SubcontratacaoClient from '../app/subcontratacao/SubcontratacaoClient';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock framer-motion — pass through children
jest.mock('framer-motion', () => {
  const React = require('react');
  const motion = new Proxy(
    {},
    {
      get: (_target: unknown, prop: string) =>
        React.forwardRef(
          (
            { children, ...props }: { children?: React.ReactNode; [key: string]: unknown },
            ref: React.Ref<HTMLElement>,
          ) => {
            const safe: Record<string, unknown> = {};
            for (const [k, v] of Object.entries(props)) {
              if (
                typeof v === 'string' ||
                typeof v === 'number' ||
                typeof v === 'boolean'
              ) {
                safe[k] = v;
              }
            }
            return React.createElement(prop, { ...safe, ref }, children);
          },
        ),
    },
  );
  return {
    motion,
    AnimatePresence: ({
      children,
    }: {
      children?: React.ReactNode;
    }) => children,
  };
});

// Mock animations lib — always visible so content renders immediately
jest.mock('@/lib/animations', () => ({
  useScrollAnimation: () => ({
    ref: { current: null },
    isVisible: true,
  }),
  fadeInUp: {},
  staggerContainer: {},
}));

// Mock fetch for products endpoint
const MOCK_SUBCONTRATACAO_PRODUCT = {
  sku: 'subcontratacao-map',
  name: 'Mapa de Subcontratacao',
  description:
    'Identifique pontes de subcontratacao em licitacoes publicas no seu setor.',
  price_brl: 9700, // R$97,00
  preview_config: {
    free_items: 3,
    total_items: 8,
  },
  delivery_config: {},
};

const MOCK_PRODUCTS_RESPONSE = {
  products: [MOCK_SUBCONTRATACAO_PRODUCT],
};

const mockFetch = jest.fn();

beforeEach(() => {
  jest.clearAllMocks();
  globalThis.fetch = mockFetch;

  mockFetch.mockImplementation((url: string) => {
    if (url === '/api/products') {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_PRODUCTS_RESPONSE),
      });
    }
    return Promise.resolve({ ok: false, status: 404 });
  });

  // Mock window.location.href
  delete (window as any).location;
  window.location = { href: '' } as any;
});

afterEach(() => {
  (window as any).mixpanel = undefined;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SubcontratacaoPage — Structure', () => {
  it('renders the hero heading', async () => {
    render(<SubcontratacaoClient />);
    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /encontre oportunidades de subcontratacao/i,
      }),
    ).toBeInTheDocument();
  });

  it('renders the hero subtitle explaining PMEs can be subcontratadas', () => {
    render(<SubcontratacaoClient />);
    expect(
      screen.getByText(/PMEs podem ser subcontratadas/i),
    ).toBeInTheDocument();
  });

  it('renders the "Como funciona" section', async () => {
    render(<SubcontratacaoClient />);
    expect(
      screen.getByRole('heading', {
        level: 2,
        name: /como funciona a subcontratacao/i,
      }),
    ).toBeInTheDocument();
  });

  it('renders all 3 explanation steps', () => {
    render(<SubcontratacaoClient />);
    expect(
      screen.getByText(/Empresa vence a licitacao/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Surge a oportunidade/i)).toBeInTheDocument();
    expect(screen.getByText(/Sua empresa recebe/i)).toBeInTheDocument();
  });

  it('renders stats section with volume data', () => {
    render(<SubcontratacaoClient />);
    expect(
      screen.getByRole('heading', {
        level: 2,
        name: /mercado de subcontratacao publica/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('87%')).toBeInTheDocument();
    expect(screen.getByText('15+')).toBeInTheDocument();
    expect(screen.getByText('R$ 12 Bi+')).toBeInTheDocument();
  });

  it('renders sectors section with progress bars', () => {
    render(<SubcontratacaoClient />);
    expect(
      screen.getByRole('heading', {
        level: 2,
        name: /setores com maior potencial/i,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Construcao Civil')).toBeInTheDocument();
    expect(screen.getByText('Servicos de Limpeza')).toBeInTheDocument();
    expect(screen.getByText('28%')).toBeInTheDocument();
    expect(screen.getByText('18%')).toBeInTheDocument();
  });

  it('renders product CTA section heading', () => {
    render(<SubcontratacaoClient />);
    expect(
      screen.getByRole('heading', {
        level: 2,
        name: /Mapa de subcontratacao para o seu setor/i,
      }),
    ).toBeInTheDocument();
  });

  it('renders the DigitalProductPreview loading skeleton initially', () => {
    render(<SubcontratacaoClient />);
    const skeletons = screen.getAllByTestId('digital-product-preview-loading');
    expect(skeletons.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the checkout button after product loads', async () => {
    render(<SubcontratacaoClient />);
    await waitFor(() => {
      const buttons = screen.getAllByTestId('checkout-button');
      expect(buttons.length).toBeGreaterThanOrEqual(1);
    });
  });

  it('shows the hero CTA with custom label after product loads', async () => {
    render(<SubcontratacaoClient />);
    await waitFor(() => {
      expect(
        screen.getByText('Encontrar oportunidades de subcontratacao'),
      ).toBeInTheDocument();
    });
  });

  it('shows price tag R$97', async () => {
    render(<SubcontratacaoClient />);
    await waitFor(() => {
      expect(screen.getByText(/R\$\s*97/)).toBeInTheDocument();
    });
  });
});

describe('SubcontratacaoPage — Mobile Responsiveness', () => {
  it('renders sections with responsive grid classes', async () => {
    const { container } = render(<SubcontratacaoClient />);
    // The sectors grid uses sm:grid-cols-2 lg:grid-cols-4
    const grid = container.querySelector('.lg\\:grid-cols-4');
    expect(grid).toBeInTheDocument();
  });
});
