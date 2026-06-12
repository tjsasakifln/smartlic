/**
 * WIDGET-COMPINT-001: Tests for Competitive Intel Widget.
 *
 * Tests:
 * - Widget embed page renders loading state
 * - Widget renders with data (all 4 themes)
 * - Widget handles error state
 * - Preview page renders builder controls
 * - Copy button generates correct code
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';

// ---------- Mock fetch ----------

const mockFetch = jest.fn();

beforeEach(() => {
  jest.resetAllMocks();
  global.fetch = mockFetch;
});

// ---------- Mock data ----------

const SHARE_DATA = {
  tema: 'market-share',
  setor: 'Hardware e Equipamentos de TI',
  uf: null,
  periodo: 'Últimos 12 meses',
  dados: {
    valor_total: 50000000,
    total_contratos: 500,
    top_fornecedores: [
      {
        nome: 'Tech Solutions Ltda',
        cnpj: '11222333000181',
        percentual: 30.0,
        valor: 15000000,
        contratos: 45,
      },
      {
        nome: 'Dados & Sistemas S.A.',
        cnpj: '44555666000199',
        percentual: 20.0,
        valor: 10000000,
        contratos: 30,
      },
    ],
    concentracao: 'Média',
  },
};

const WINNERS_DATA = {
  tema: 'top-winners',
  setor: 'Hardware e Equipamentos de TI',
  uf: 'SP',
  periodo: 'Últimos 12 meses',
  dados: {
    winners: [
      { nome: 'Tech Solutions Ltda', cnpj: '11222333000181', contratos: 45, valor_total: 15000000, crescimento: null },
      { nome: 'Dados & Sistemas S.A.', cnpj: '44555666000199', contratos: 30, valor_total: 10000000, crescimento: null },
    ],
  },
};

const TREND_DATA = {
  tema: 'monthly-trend',
  setor: 'Hardware e Equipamentos de TI',
  uf: null,
  periodo: 'Últimos 12 meses',
  dados: {
    serie: [
      { mes: '2025-07', valor: 4000000, contratos: 40 },
      { mes: '2025-12', valor: 4800000, contratos: 48 },
      { mes: '2026-06', valor: 6000000, contratos: 60 },
    ],
    tendencia: 'crescimento',
  },
};

const ORGAO_DATA = {
  tema: 'orgao-ranking',
  setor: 'Hardware e Equipamentos de TI',
  uf: null,
  periodo: 'Últimos 12 meses',
  dados: {
    orgaos: [
      { nome: 'Secretaria de Tecnologia', cnpj: '12345678000190', valor: 8000000, contratos: 25 },
      { nome: 'Ministério da Gestão', cnpj: '98765432000110', valor: 6000000, contratos: 20 },
    ],
  },
};

// ---------- Helper to mock search params ----------

function mockSearchParams(setor: string, tema: string, uf?: string) {
  const params = new URLSearchParams({ setor, tema });
  if (uf) params.set('uf', uf);

  // jsdom doesn't implement URLSearchParams on window.location
  // We need to mock it
  delete (window as Record<string, unknown>).location;
  (window as Record<string, unknown>).location = {
    ...window.location,
    search: `?${params.toString()}`,
    href: `https://smartlic.tech/widgets/competitive-intel?${params.toString()}`,
  };
}

// ---------- Tests: Widget embed ----------

describe('Widget Competitive Intel Page', () => {
  beforeEach(() => {
    // Reset URL
    delete (window as Record<string, unknown>).location;
    (window as Record<string, unknown>).location = {
      ...window.location,
      search: '',
      href: 'https://smartlic.tech/widgets/competitive-intel',
    };
  });

  // eslint-disable-next-line jest/expect-expect
  it('renderiza estado de carregamento', async () => {
    mockSearchParams('informatica', 'market-share');

    // Return a promise that never resolves to test loading state
    mockFetch.mockImplementationOnce(
      () => new Promise(() => {})
    );

    // Dynamic import to avoid module evaluation issues
    const WidgetPage = (await import('../app/widgets/competitive-intel/page')).default;
    render(<WidgetPage />);

    expect(screen.getByText('Carregando dados...')).toBeInTheDocument();
  });

  it('renderiza market-share widget com dados', async () => {
    mockSearchParams('informatica', 'market-share');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => SHARE_DATA,
    });

    const WidgetPage = (await import('../app/widgets/competitive-intel/page')).default;
    render(<WidgetPage />);

    await screen.findByText(/Market Share/, undefined, { timeout: 5000 });
    expect(screen.getByText('Tech Solutions Ltda')).toBeInTheDocument();
    expect(screen.getByText('Dados & Sistemas S.A.')).toBeInTheDocument();
  });

  it('renderiza top-winners widget com dados', async () => {
    mockSearchParams('informatica', 'top-winners');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => WINNERS_DATA,
    });

    const WidgetPage = (await import('../app/widgets/competitive-intel/page')).default;
    render(<WidgetPage />);

    await screen.findByText(/Top Vencedores/, undefined, { timeout: 5000 });
  });

  it('renderiza monthly-trend widget com dados', async () => {
    mockSearchParams('informatica', 'monthly-trend');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => TREND_DATA,
    });

    const WidgetPage = (await import('../app/widgets/competitive-intel/page')).default;
    render(<WidgetPage />);

    await screen.findByText(/Tendência Mensal/, undefined, { timeout: 5000 });
    expect(screen.getByText(/em crescimento/)).toBeInTheDocument();
  });

  it('renderiza orgao-ranking widget com dados', async () => {
    mockSearchParams('informatica', 'orgao-ranking');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ORGAO_DATA,
    });

    const WidgetPage = (await import('../app/widgets/competitive-intel/page')).default;
    render(<WidgetPage />);

    await screen.findByText(/Ranking de Órgãos/, undefined, { timeout: 5000 });
    expect(screen.getByText('Secretaria de Tecnologia')).toBeInTheDocument();
  });

  it('exibe footer com atribuicao SmartLic', async () => {
    mockSearchParams('informatica', 'market-share');
    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => SHARE_DATA,
    });

    const WidgetPage = (await import('../app/widgets/competitive-intel/page')).default;
    render(<WidgetPage />);

    await waitFor(() => {
      expect(screen.getByText(/Dados por/)).toBeInTheDocument();
    });

    const links = screen.getAllByRole('link');
    const smartlicLink = links.find((l) => l.textContent?.includes('SmartLic'));
    expect(smartlicLink).toBeInTheDocument();
    expect(smartlicLink).toHaveAttribute('href', 'https://smartlic.tech');
  });

  it('exibe mensagem de erro quando fetch falha', async () => {
    mockSearchParams('informatica', 'market-share');
    mockFetch.mockRejectedValueOnce(new Error('Erro de conexão'));

    const WidgetPage = (await import('../app/widgets/competitive-intel/page')).default;
    render(<WidgetPage />);

    await waitFor(() => {
      expect(screen.getByText('Erro de conexão')).toBeInTheDocument();
    });
  });

  it('exibe erro para parametros faltando', async () => {
    // No params set
    const WidgetPage = (await import('../app/widgets/competitive-intel/page')).default;
    render(<WidgetPage />);

    await waitFor(() => {
      expect(screen.getByText(/Parâmetros obrigatórios/)).toBeInTheDocument();
    });
  });
});

// ---------- Tests: Preview page ----------

describe('Widget Preview Page', () => {
  it('renderiza controles do builder', async () => {
    const PreviewPage = (await import('../app/widgets/competitive-intel/preview/page')).default;
    render(<PreviewPage />);

    expect(screen.getByText('Widget de Inteligência Competitiva')).toBeInTheDocument();
    expect(screen.getByLabelText('Setor')).toBeInTheDocument();
    expect(screen.getByLabelText(/UF/)).toBeInTheDocument();
    expect(screen.getByText('Market Share')).toBeInTheDocument();
    expect(screen.getByText('Top Vencedores')).toBeInTheDocument();
    expect(screen.getByText('Tendência Mensal')).toBeInTheDocument();
    expect(screen.getByText('Ranking de Órgãos')).toBeInTheDocument();
  });

  it('renderiza iframe de preview', async () => {
    const PreviewPage = (await import('../app/widgets/competitive-intel/preview/page')).default;
    render(<PreviewPage />);

    const iframe = screen.getByTitle('Widget Preview');
    expect(iframe).toBeInTheDocument();
    expect(iframe).toHaveAttribute('src');
    expect(iframe.getAttribute('src')).toContain('/widgets/competitive-intel');
  });

  it('botao de copiar funciona', async () => {
    // Mock clipboard
    const writeText = jest.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: { writeText },
    });

    const PreviewPage = (await import('../app/widgets/competitive-intel/preview/page')).default;
    render(<PreviewPage />);

    const copyButton = screen.getByText('Copiar');
    await userEvent.click(copyButton);

    await waitFor(() => {
      expect(screen.getByText('Copiado!')).toBeInTheDocument();
    });

    // Verify embed code was copied
    expect(writeText).toHaveBeenCalled();
    const embedCode = writeText.mock.calls[0][0];
    expect(embedCode).toContain('<iframe');
    expect(embedCode).toContain('/widgets/competitive-intel');
    expect(embedCode).toContain('smartlic.tech');
  });
});
