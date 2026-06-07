import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';

/**
 * Tests for API-SELF-006: /conta/api usage dashboard.
 */

let mockUseUser = {
  user: { id: 'user-1', email: 'test@test.com' },
  session: { access_token: 'fake-token' },
  authLoading: false,
  planInfo: null,
  planError: null,
  isFromCache: false,
  cachedAt: null,
  refresh: jest.fn(),
};

// Mock Next.js Link
jest.mock('next/link', () => {
  return function MockLink({ children, href, ...props }: any) {
    return <a href={href} {...props}>{children}</a>;
  };
});

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/conta/api',
}));

// Mock useUser context
jest.mock('../contexts/UserContext', () => ({
  useUser: () => mockUseUser,
}));

// Mock Recharts (canvas-based, needs jsdom workaround)
jest.mock('recharts', () => {
  const React = require('react');
  return {
    __esModule: true,
    ResponsiveContainer: ({ children }: any) => React.createElement('div', { 'data-testid': 'chart-container' }, children),
    BarChart: ({ children }: any) => React.createElement('div', { 'data-testid': 'bar-chart' }, children),
    Bar: () => React.createElement('div', { 'data-testid': 'bar' }),
    XAxis: () => React.createElement('div', { 'data-testid': 'xaxis' }),
    YAxis: () => React.createElement('div', { 'data-testid': 'yaxis' }),
    CartesianGrid: () => React.createElement('div', { 'data-testid': 'cartesian-grid' }),
    Tooltip: () => React.createElement('div', { 'data-testid': 'tooltip' }),
    ReferenceLine: () => React.createElement('div', { 'data-testid': 'reference-line' }),
  };
});

import ApiUsagePage from '../app/conta/api/page';

const mockApiData = {
  api_keys: [
    {
      id: 'key-1-uuid',
      name: 'Minha Chave',
      created_at: '2026-06-01T00:00:00Z',
      last_used_at: '2026-06-05T12:00:00Z',
      revoked_at: null,
    },
  ],
  current_month_usage: 450,
  monthly_limit: 1000,
  tier: 'starter',
  daily_usage: [
    { date: '2026-06-01', count: 100 },
    { date: '2026-06-02', count: 150 },
    { date: '2026-06-03', count: 80 },
    { date: '2026-06-04', count: 70 },
    { date: '2026-06-05', count: 50 },
  ],
  month: '2026-06',
};

describe('API Usage Dashboard (API-SELF-006)', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockApiData),
    });
    jest.clearAllMocks();
  });

  it('renders loading skeleton when auth is loading', () => {
    mockUseUser = {
      ...mockUseUser,
      authLoading: true,
      user: null,
      session: null,
    };
    render(<ApiUsagePage />);
    expect(screen.getByText('Carregando...')).toBeInTheDocument();
    // Restore
    mockUseUser = {
      ...mockUseUser,
      authLoading: false,
      user: { id: 'user-1', email: 'test@test.com' },
      session: { access_token: 'fake-token' },
    };
  });

  it('renders tier label after data loads', async () => {
    render(<ApiUsagePage />);
    await waitFor(() => {
      expect(screen.getByText(/Plano Starter/i)).toBeInTheDocument();
    });
  });

  it('renders API keys section after load', async () => {
    render(<ApiUsagePage />);
    await waitFor(() => {
      expect(screen.getByText(/Suas Chaves de API/i)).toBeInTheDocument();
    });
  });

  it('renders daily usage chart after load', async () => {
    render(<ApiUsagePage />);
    await waitFor(() => {
      expect(screen.getByTestId('chart-container')).toBeInTheDocument();
    });
  });

  it('renders rate limits info section', async () => {
    render(<ApiUsagePage />);
    await waitFor(() => {
      expect(screen.getByText('Rate Limits')).toBeInTheDocument();
    });
  });

  it('shows login prompt when not authenticated', () => {
    // Override the module-level variable for unauthenticated state
    mockUseUser = {
      user: null,
      session: null,
      authLoading: false,
      planInfo: null,
      planError: null,
      isFromCache: false,
      cachedAt: null,
      refresh: jest.fn(),
    };

    render(<ApiUsagePage />);
    expect(screen.getByText('Ir para login')).toBeInTheDocument();

    // Restore for subsequent tests
    mockUseUser = {
      user: { id: 'user-1', email: 'test@test.com' },
      session: { access_token: 'fake-token' },
      authLoading: false,
      planInfo: null,
      planError: null,
      isFromCache: false,
      cachedAt: null,
      refresh: jest.fn(),
    };
  });
});
