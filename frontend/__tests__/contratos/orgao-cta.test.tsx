/**
 * CONV-CTA-001: Validates hero + footer CTAs on /contratos/orgao/[cnpj] page.
 *
 * Tests:
 * - 2 TrackingLink CTAs present (hero + footer)
 * - UTM params correct in both hrefs
 * - page_cnpj param present
 * - trackEvent fired with correct eventProps on click
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';

const mockTrackEvent = jest.fn();

jest.mock('@/hooks/useAnalytics', () => ({
  useAnalytics: () => ({ trackEvent: mockTrackEvent }),
}));

jest.mock('next/link', () => {
  const MockLink = ({ href, children, className, onClick, ...rest }: {
    href: string;
    children: React.ReactNode;
    className?: string;
    onClick?: () => void;
    [key: string]: unknown;
  }) => (
    <a href={href} className={className} onClick={onClick} {...rest}>
      {children}
    </a>
  );
  MockLink.displayName = 'MockLink';
  return MockLink;
});

jest.mock('@/components/LeadCapture', () => ({
  LeadCapture: ({ heading }: { heading: string }) => <div data-testid="lead-capture">{heading}</div>,
}));

jest.mock('@/app/components/landing/LandingNavbar', () => ({
  __esModule: true,
  default: () => <nav data-testid="navbar" />,
}));

jest.mock('@/app/components/Footer', () => ({
  __esModule: true,
  default: () => <footer data-testid="footer" />,
}));

// Mock fetch for page data
const mockStats = {
  orgao_nome: 'Prefeitura Municipal de Teste',
  orgao_cnpj: '12345678000100',
  total_contracts: 42,
  total_value: 1000000,
  avg_value: 23809,
  top_fornecedores: [],
  monthly_trend: [],
  sample_contracts: [],
  last_updated: '2026-04-01T00:00:00Z',
  aviso_legal: 'Dados de carater informativo.',
};

beforeEach(() => {
  mockTrackEvent.mockClear();
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => mockStats,
  });
});

afterEach(() => {
  jest.restoreAllMocks();
});

async function renderPage(cnpj = '12345678000100') {
  const { default: OrgaoContratosPage } = await import(
    '@/app/contratos/orgao/[cnpj]/page'
  );
  const props = { params: Promise.resolve({ cnpj }) };
  const jsx = await OrgaoContratosPage(props);
  return render(jsx as React.ReactElement);
}

describe('CONV-CTA-001: /contratos/orgao/[cnpj] CTAs', () => {
  it('renders hero CTA with correct text', async () => {
    await renderPage();
    expect(screen.getByText('Teste gratis por 14 dias')).toBeInTheDocument();
  });

  it('renders footer CTA with correct text', async () => {
    await renderPage();
    expect(screen.getByText('Comecar teste gratis')).toBeInTheDocument();
  });

  it('both CTAs have UTM params in href', async () => {
    const cnpj = '12345678000100';
    await renderPage(cnpj);

    const links = screen.getAllByRole('link', {
      name: /teste gratis|comecar teste gratis/i,
    });
    expect(links).toHaveLength(2);

    for (const link of links) {
      const href = link.getAttribute('href') ?? '';
      expect(href).toContain('utm_source=programmatic');
      expect(href).toContain('utm_medium=cta');
      expect(href).toContain('utm_campaign=conv-cta-001');
      expect(href).toContain('utm_content=contratos-orgao');
      expect(href).toContain(`page_cnpj=${cnpj}`);
    }
  });

  it('hero CTA fires cta_clicked with hero placement on click', async () => {
    await renderPage();
    const heroLink = screen.getByText('Teste gratis por 14 dias');
    fireEvent.click(heroLink);
    expect(mockTrackEvent).toHaveBeenCalledWith(
      'cta_clicked',
      expect.objectContaining({ cta_name: 'contratos_orgao_hero', placement: 'hero' })
    );
  });

  it('footer CTA fires cta_clicked with footer placement on click', async () => {
    await renderPage();
    const footerLink = screen.getByText('Comecar teste gratis');
    fireEvent.click(footerLink);
    expect(mockTrackEvent).toHaveBeenCalledWith(
      'cta_clicked',
      expect.objectContaining({ cta_name: 'contratos_orgao_footer', placement: 'footer' })
    );
  });

  it('LeadCapture still renders as secondary element', async () => {
    await renderPage();
    expect(screen.getByTestId('lead-capture')).toBeInTheDocument();
  });
});
