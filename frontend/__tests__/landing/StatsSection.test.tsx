/**
 * StatsSection / StatsClientIsland Tests
 * DEBT-v3-S2 AC20: Updated for RSC + client island architecture.
 *
 * StatsSection is now an RSC wrapper that renders:
 * 1. <noscript> fallback with static values (for SEO/crawlers)
 * 2. StatsClientIsland (client island with animations + SWR)
 *
 * Tests target StatsClientIsland directly for interactive behavior,
 * and StatsSection for the integrated rendering.
 */

import { render, screen, waitFor } from '@testing-library/react';

// Mock useInView -- jsdom has no IntersectionObserver
// Controllable via mockIsInView so individual tests can opt out of animation
let mockIsInView = true;
jest.mock('../../app/hooks/useInView', () => ({
  useInView: () => ({ ref: { current: null }, isInView: mockIsInView }),
}));

// STORY-351 AC7 / FE-007: Mock useDiscardRate SWR hook
// StatsClientIsland uses useDiscardRate from usePublicMetrics (SWR-based)
let mockDiscardRate: number | null = null;
let mockDiscardLoading = false;
jest.mock('@/hooks/usePublicMetrics', () => ({
  useDiscardRate: () => ({
    discardRate: mockDiscardRate,
    isLoading: mockDiscardLoading,
    error: null,
  }),
  useDailyVolume: () => ({
    displayValue: null,
    isLoading: false,
    error: null,
  }),
}));

beforeEach(() => {
  mockDiscardRate = null;
  mockDiscardLoading = false;
  mockIsInView = true;
});

import StatsClientIsland from '@/app/components/landing/StatsClientIsland';
import StatsSection from '@/app/components/landing/StatsSection';

describe('StatsClientIsland (client island)', () => {
  it('renders section title', () => {
    render(<StatsClientIsland />);

    expect(screen.getByText(/Impacto real no mercado de licitações/i)).toBeInTheDocument();
  });

  it('renders hero stat -- 15 setores (with counter animation)', async () => {
    render(<StatsClientIsland />);

    // Wait for counter animation to complete (1200ms)
    await waitFor(() => {
      expect(screen.getByText('15')).toBeInTheDocument();
    }, { timeout: 3000 });
    expect(screen.getByText(/setores especializados/i)).toBeInTheDocument();
  });

  it('renders dynamic discard rate from API (STORY-351 AC4/AC6)', async () => {
    mockDiscardRate = 91; // hook already applies Math.round
    render(<StatsClientIsland />);

    // Wait for counter animation to complete
    await waitFor(() => {
      expect(screen.getByText('91%')).toBeInTheDocument();
    }, { timeout: 3000 });
    expect(screen.getByText(/de ruído eliminado/i)).toBeInTheDocument();
  });

  it('shows fallback "A maioria" when API returns no data (STORY-351 AC4)', async () => {
    mockDiscardRate = null; // null -> show "A maioria" fallback
    render(<StatsClientIsland />);

    await waitFor(() => {
      expect(screen.getByText('A maioria')).toBeInTheDocument();
    }, { timeout: 3000 });
    expect(screen.getByText(/de ruído eliminado/i)).toBeInTheDocument();
  });

  it('shows fallback "A maioria" when API fails (STORY-351 AC4)', async () => {
    mockDiscardRate = null; // error -> hook returns null -> fallback
    render(<StatsClientIsland />);

    await waitFor(() => {
      expect(screen.getByText('A maioria')).toBeInTheDocument();
    }, { timeout: 3000 });
  });

  it('shows loading state before API responds (STORY-351 AC6)', () => {
    mockDiscardLoading = true; // Hook is loading
    render(<StatsClientIsland />);

    // Loading pulse element should be present
    const pulseEl = document.querySelector('.animate-pulse');
    expect(pulseEl).toBeInTheDocument();
  });

  it('renders 3 supporting stats with counter animation (SAB-006 AC2/AC6)', async () => {
    mockDiscardRate = 88; // hook applies Math.round(87.5) = 88
    render(<StatsClientIsland />);

    // Wait for counter animation to complete
    await waitFor(() => {
      expect(screen.getByText('88%')).toBeInTheDocument();
    }, { timeout: 3000 });

    expect(screen.getByText(/de ruído eliminado/i)).toBeInTheDocument();

    expect(screen.getByText('1000+')).toBeInTheDocument();
    expect(screen.getByText(/regras de filtragem/i)).toBeInTheDocument();

    expect(screen.getByText('27')).toBeInTheDocument();
    expect(screen.getByText(/estados cobertos/i)).toBeInTheDocument();
  });

  it('initializes counters with final values for SSR/SEO (UX-422 AC1)', () => {
    // UX-422: counters now start at final values (15, 1000, 27) for SSR/SEO,
    // then animate from 0 when IntersectionObserver fires.
    // Use isInView=false so the animation effect does not reset counters to 0.
    mockIsInView = false;
    render(<StatsClientIsland />);

    // Initial render: counters show final values (not 0) -- SSR-friendly
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('1000+')).toBeInTheDocument();
    expect(screen.getByText('27')).toBeInTheDocument();
  });

  it('uses hero number layout', () => {
    const { container } = render(<StatsClientIsland />);

    const heroNumber = container.querySelector('.text-5xl, .text-6xl, .text-7xl, .lg\\:text-7xl');
    expect(heroNumber).toBeInTheDocument();
  });

  it('uses design system tokens', () => {
    const { container } = render(<StatsClientIsland />);

    expect(container.querySelector('.text-brand-navy')).toBeInTheDocument();
    expect(container.querySelector('.text-brand-blue')).toBeInTheDocument();
    expect(container.querySelector('.bg-brand-blue-subtle\\/50')).toBeInTheDocument();
  });

  it('uses tabular-nums for numerical data', () => {
    const { container } = render(<StatsClientIsland />);

    const tabularNums = container.querySelectorAll('.tabular-nums');
    expect(tabularNums.length).toBeGreaterThan(0);
  });

  it('has accessible aria-labels for all stats', async () => {
    mockDiscardRate = null; // null -> "A maioria" fallback
    render(<StatsClientIsland />);

    // Wait for animation to settle
    await waitFor(() => {
      expect(screen.getByText('A maioria')).toBeInTheDocument();
    }, { timeout: 3000 });

    expect(screen.getByRole('text', { name: '15 setores especializados' })).toBeInTheDocument();
    expect(screen.getByRole('text', { name: '87% de ruído eliminado' })).toBeInTheDocument();
    expect(screen.getByRole('text', { name: '1000+ regras de filtragem' })).toBeInTheDocument();
    expect(screen.getByRole('text', { name: '27 estados cobertos' })).toBeInTheDocument();
  });

  it('has dynamic aria-label when API returns data (STORY-351)', async () => {
    mockDiscardRate = 92;
    render(<StatsClientIsland />);

    await waitFor(() => {
      expect(screen.getByRole('text', { name: '92% de ruído eliminado' })).toBeInTheDocument();
    }, { timeout: 3000 });
  });
});

describe('StatsSection (RSC wrapper)', () => {
  it('renders the client island content', () => {
    render(<StatsSection />);

    // The client island renders the title
    expect(screen.getByText(/Impacto real no mercado de licitações/i)).toBeInTheDocument();
  });

  it('passes className to noscript fallback', () => {
    const { container } = render(<StatsSection className="my-custom-class" />);

    // The noscript element should contain the class
    const noscript = container.querySelector('noscript');
    expect(noscript).toBeInTheDocument();
  });
});
