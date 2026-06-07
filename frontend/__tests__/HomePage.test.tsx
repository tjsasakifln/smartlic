/**
 * Tests for Homepage refatorada como terminal de inteligencia — CONV-010-3 (#1510)
 *
 * Covers:
 * - Renders search bar
 * - Renders 6 intent cards
 * - Card clicks fire Mixpanel
 * - Search submit navigates correctly
 * - Intent detection banner shows when intent detected
 * - Mobile responsive classes present
 * - Old hero/feature-grid sections removed
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import IntelHomeClient from '../app/components/conversion/IntelHomeClient';
import type { IntentCluster } from '../app/components/conversion/IntentRouter';

// ── Mocks ───────────────────────────────────────────────────────────────

const mockPush = jest.fn();

// Mock next/navigation — override global jest.setup mock for specific push
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => '/',
  useSearchParams: () => new URLSearchParams(),
}));

// Mock mixpanel-browser
const mockMixpanelTrack = jest.fn();
jest.mock('mixpanel-browser', () => ({
  track: (...args: unknown[]) => mockMixpanelTrack(...args),
  init: jest.fn(),
  identify: jest.fn(),
  people: { set: jest.fn() },
  opt_out_tracking: jest.fn(),
  opt_in_tracking: jest.fn(),
  register: jest.fn(),
}));

// Mock IntentRouter for controlled intent detection
const mockUseIntentDetection = jest.fn();
jest.mock('../app/components/conversion/IntentRouter', () => ({
  ...jest.requireActual('../app/components/conversion/IntentRouter'),
  useIntentDetection: () => mockUseIntentDetection(),
}));

// ── Setup ────────────────────────────────────────────────────────────────

beforeEach(() => {
  jest.clearAllMocks();
  // Default: no intent detected (geral)
  mockUseIntentDetection.mockReturnValue({ cluster: 'geral' as IntentCluster, source: 'fallback' });
});

// ── Tests ────────────────────────────────────────────────────────────────

describe('Homepage Intel Terminal — Structure', () => {
  it('renders the main heading', () => {
    render(<IntelHomeClient />);
    expect(
      screen.getByRole('heading', {
        level: 1,
        name: /terminal de inteligencia/i,
      }),
    ).toBeInTheDocument();
  });

  it('renders the subtitle', () => {
    render(<IntelHomeClient />);
    expect(
      screen.getByText(/Busque editais, analise concorrentes/i),
    ).toBeInTheDocument();
  });

  it('renders the search bar with placeholder', () => {
    render(<IntelHomeClient />);
    const searchInput = screen.getByTestId('search-input');
    expect(searchInput).toBeInTheDocument();
    expect(searchInput).toHaveAttribute(
      'placeholder',
      'Busque editais, fornecedores, orgaos...',
    );
  });

  it('renders the sector selector dropdown', () => {
    render(<IntelHomeClient />);
    const select = screen.getByTestId('sector-select');
    expect(select).toBeInTheDocument();
    expect(select).toHaveDisplayValue('Todos os setores');
  });

  it('renders the Buscar button', () => {
    render(<IntelHomeClient />);
    const button = screen.getByTestId('search-submit');
    expect(button).toBeInTheDocument();
    expect(button).toHaveTextContent('Buscar');
  });

  it('renders all 6 intent cards', () => {
    render(<IntelHomeClient />);
    const cardIds = ['vender', 'pesquisar', 'parceiros', 'mercado', 'acompanhar', 'preparar'];
    for (const id of cardIds) {
      expect(screen.getByTestId(`intent-card-${id}`)).toBeInTheDocument();
    }
  });

  it('renders only 6 intent cards (no more, no less)', () => {
    render(<IntelHomeClient />);
    const cards = screen.getAllByTestId(/^intent-card-/);
    expect(cards).toHaveLength(6);
  });

  it('renders "Saiba mais" on each card', () => {
    render(<IntelHomeClient />);
    const saibaMaisLinks = screen.getAllByText(/Saiba mais/i);
    expect(saibaMaisLinks).toHaveLength(6);
  });
});

describe('Homepage Intel Terminal — Intent Detection Banner', () => {
  it('does NOT show intent banner when cluster is "geral"', () => {
    mockUseIntentDetection.mockReturnValue({ cluster: 'geral' as IntentCluster, source: 'fallback' });
    render(<IntelHomeClient />);
    expect(screen.queryByTestId('intent-banner')).not.toBeInTheDocument();
  });

  it('shows intent banner when cluster is "comercial"', () => {
    mockUseIntentDetection.mockReturnValue({ cluster: 'comercial' as IntentCluster, source: 'search_term' });
    render(<IntelHomeClient />);
    expect(screen.getByTestId('intent-banner')).toBeInTheDocument();
    expect(screen.getByText(/oportunidades comerciais/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Acessar/i })).toHaveAttribute('href', '/para-empresas');
  });

  it('shows intent banner when cluster is "juridica"', () => {
    mockUseIntentDetection.mockReturnValue({ cluster: 'juridica' as IntentCluster, source: 'referrer' });
    render(<IntelHomeClient />);
    expect(screen.getByTestId('intent-banner')).toBeInTheDocument();
    expect(screen.getByText(/informacoes juridicas/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Acessar/i })).toHaveAttribute('href', '/para-advogados');
  });

  it('shows intent banner when cluster is "investigativa"', () => {
    mockUseIntentDetection.mockReturnValue({ cluster: 'investigativa' as IntentCluster, source: 'search_term' });
    render(<IntelHomeClient />);
    expect(screen.getByTestId('intent-banner')).toBeInTheDocument();
    expect(screen.getByText(/analise de mercado/i)).toBeInTheDocument();
  });

  it('shows intent banner when cluster is "subcontratacao"', () => {
    mockUseIntentDetection.mockReturnValue({ cluster: 'subcontratacao' as IntentCluster, source: 'referrer' });
    render(<IntelHomeClient />);
    expect(screen.getByTestId('intent-banner')).toBeInTheDocument();
    expect(screen.getByText(/parceiros e subcontratacao/i)).toBeInTheDocument();
  });

  it('fires home_intent_routed event when intent is detected', () => {
    mockUseIntentDetection.mockReturnValue({ cluster: 'comercial' as IntentCluster, source: 'search_term' });
    render(<IntelHomeClient />);
    expect(mockMixpanelTrack).toHaveBeenCalledWith('home_intent_routed', {
      cluster: 'comercial',
      source: 'search_term',
    });
  });

  it('does NOT fire home_intent_routed for geral cluster', () => {
    mockUseIntentDetection.mockReturnValue({ cluster: 'geral' as IntentCluster, source: 'fallback' });
    render(<IntelHomeClient />);
    expect(mockMixpanelTrack).not.toHaveBeenCalledWith('home_intent_routed', expect.anything());
  });
});

describe('Homepage Intel Terminal — Search Behavior', () => {
  it('disables the submit button when input is empty', () => {
    render(<IntelHomeClient />);
    const button = screen.getByTestId('search-submit');
    expect(button).toBeDisabled();
  });

  it('enables the submit button when input has text', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    const input = screen.getByTestId('search-input');
    await user.type(input, 'obras publicas');
    expect(screen.getByTestId('search-submit')).not.toBeDisabled();
  });

  it('navigates to /buscar?q=... on search submit', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    const input = screen.getByTestId('search-input');
    await user.type(input, 'construcao civil');
    await user.click(screen.getByTestId('search-submit'));
    expect(mockPush).toHaveBeenCalledWith('/buscar?q=construcao+civil');
  });

  it('includes setor param in navigation when sector selected', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    const input = screen.getByTestId('search-input');
    const select = screen.getByTestId('sector-select');

    await user.type(input, 'hospital equipamentos');
    await user.selectOptions(select, 'saude');
    await user.click(screen.getByTestId('search-submit'));

    expect(mockPush).toHaveBeenCalledWith(expect.stringContaining('q=hospital+equipamentos'));
    expect(mockPush).toHaveBeenCalledWith(expect.stringContaining('setor=saude'));
  });

  it('fires home_search_initiated Mixpanel event on search', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    const input = screen.getByTestId('search-input');
    await user.type(input, 'tecnologia governo');
    await user.click(screen.getByTestId('search-submit'));
    expect(mockMixpanelTrack).toHaveBeenCalledWith('home_search_initiated', {
      query: 'tecnologia governo',
      sector: '',
    });
  });

  it('does not navigate when search is empty', async () => {
    render(<IntelHomeClient />);
    const form = screen.getByTestId('home-search-form');
    fireEvent.submit(form);
    expect(mockPush).not.toHaveBeenCalled();
  });
});

describe('Homepage Intel Terminal — Intent Cards Behavior', () => {
  it('navigates to /para-empresas when card "vender" is clicked', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    await user.click(screen.getByTestId('intent-card-vender'));
    expect(mockPush).toHaveBeenCalledWith('/para-empresas');
  });

  it('navigates to /buscar when card "pesquisar" is clicked', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    await user.click(screen.getByTestId('intent-card-pesquisar'));
    expect(mockPush).toHaveBeenCalledWith('/buscar');
  });

  it('navigates to /para-fornecedores when card "parceiros" is clicked', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    await user.click(screen.getByTestId('intent-card-parceiros'));
    expect(mockPush).toHaveBeenCalledWith('/para-fornecedores');
  });

  it('navigates to /observatorio when card "mercado" is clicked', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    await user.click(screen.getByTestId('intent-card-mercado'));
    expect(mockPush).toHaveBeenCalledWith('/observatorio');
  });

  it('navigates to /signup?source=intent-home when card "acompanhar" is clicked', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    await user.click(screen.getByTestId('intent-card-acompanhar'));
    expect(mockPush).toHaveBeenCalledWith('/signup?source=intent-home');
  });

  it('navigates to /para-advogados when card "preparar" is clicked', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    await user.click(screen.getByTestId('intent-card-preparar'));
    expect(mockPush).toHaveBeenCalledWith('/para-advogados');
  });

  it('fires home_intent_card_click Mixpanel event on card click', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    await user.click(screen.getByTestId('intent-card-vender'));
    expect(mockMixpanelTrack).toHaveBeenCalledWith('home_intent_card_click', {
      card_id: 'vender',
      card_title: 'Quero vender para o governo',
    });
  });

  it('fires Mixpanel event with correct card data for each card', async () => {
    const user = userEvent.setup();
    render(<IntelHomeClient />);
    await user.click(screen.getByTestId('intent-card-mercado'));
    expect(mockMixpanelTrack).toHaveBeenCalledWith('home_intent_card_click', {
      card_id: 'mercado',
      card_title: 'Quero entender meu mercado',
    });
  });
});

describe('Homepage Intel Terminal — Mobile Responsive Classes', () => {
  it('has 2-column grid class on mobile', () => {
    render(<IntelHomeClient />);
    const grid = screen.getByTestId('intent-cards-section').querySelector('.grid');
    expect(grid).toHaveClass('grid-cols-2');
  });

  it('has 3-column grid class on desktop', () => {
    render(<IntelHomeClient />);
    const grid = screen.getByTestId('intent-cards-section').querySelector('.grid');
    expect(grid).toHaveClass('md:grid-cols-3');
  });

  it('has card hover shadow classes', () => {
    render(<IntelHomeClient />);
    const card = screen.getByTestId('intent-card-vender');
    expect(card).toHaveClass('shadow-sm');
    expect(card).toHaveClass('hover:shadow-md');
  });

  it('has card hover translate effect', () => {
    render(<IntelHomeClient />);
    const card = screen.getByTestId('intent-card-vender');
    expect(card).toHaveClass('hover:-translate-y-1');
  });

  it('has card border and rounded classes', () => {
    render(<IntelHomeClient />);
    const card = screen.getByTestId('intent-card-vender');
    expect(card).toHaveClass('rounded-xl');
    expect(card).toHaveClass('border');
  });
});

describe('Homepage Intel Terminal — Old Sections Removed', () => {
  it('does NOT render old hero section elements', () => {
    render(<IntelHomeClient />);
    // These were in the old page — ensure they are gone
    expect(screen.queryByText(/Antecipe.*Decida.*Execute/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Terminal Comparison/i)).not.toBeInTheDocument();
  });

  it('does NOT render old feature grid elements', () => {
    render(<IntelHomeClient />);
    // Old pricing section should be gone
    expect(screen.queryByText(/PricingSectionB2G/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Precos/i)).not.toBeInTheDocument();
  });

  it('uses semantic HTML with main landmark', () => {
    render(<IntelHomeClient />);
    expect(screen.getByRole('main')).toBeInTheDocument();
  });

  it('uses h1 for the main heading', () => {
    render(<IntelHomeClient />);
    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });
});

describe('Homepage Intel Terminal — Card Content', () => {
  // Verify each card has its emoji, title, and description
  const cardData = [
    { id: 'vender', title: 'vender', description: 'Encontre editais' },
    { id: 'pesquisar', title: 'pesquisar', description: 'Analise de quem ganha' },
    { id: 'parceiros', title: 'parceiros', description: 'subcontratacao' },
    { id: 'mercado', title: 'mercado', description: 'tendencias' },
    { id: 'acompanhar', title: 'acompanhar', description: 'Alertas personalizados' },
    { id: 'preparar', title: 'preparar', description: 'Checklist' },
  ];

  for (const card of cardData) {
    it(`card "${card.id}" has correct content`, () => {
      render(<IntelHomeClient />);
      expect(screen.getByTestId(`intent-card-${card.id}`)).toHaveTextContent(
        new RegExp(card.title, 'i'),
      );
      expect(screen.getByTestId(`intent-card-${card.id}`)).toHaveTextContent(
        new RegExp(card.description, 'i'),
      );
    });
  }
});
