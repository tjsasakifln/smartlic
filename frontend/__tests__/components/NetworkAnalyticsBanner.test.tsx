import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import NetworkAnalyticsBanner from '../../components/NetworkAnalyticsBanner';

// Mock UserContext
const mockUser = {
  id: 'user-1',
  email: 'test@example.com',
  allow_network_analytics: undefined,
};

let mockUserValue: { user: typeof mockUser | null } = { user: mockUser };

jest.mock('../../contexts/UserContext', () => ({
  useUser: () => mockUserValue,
}));

// Mock fetch
global.fetch = jest.fn();

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value; },
    removeItem: (key: string) => { delete store[key]; },
    clear: () => { store = {}; },
  };
})();
Object.defineProperty(window, 'localStorage', { value: localStorageMock });

describe('NetworkAnalyticsBanner', () => {
  beforeEach(() => {
    localStorageMock.clear();
    jest.clearAllMocks();
    mockUserValue = { user: { ...mockUser } };
  });

  it('renders when user has not decided (allow_network_analytics is undefined)', () => {
    render(<NetworkAnalyticsBanner />);
    expect(
      screen.getByText(/SmartLic agora aprende com o uso coletivo/i)
    ).toBeInTheDocument();
  });

  it('shows Activate button', () => {
    render(<NetworkAnalyticsBanner />);
    expect(
      screen.getByRole('button', { name: /Ativar contribuicao/i })
    ).toBeInTheDocument();
  });

  it('shows Saiba mais link', () => {
    render(<NetworkAnalyticsBanner />);
    const link = screen.getByRole('link', { name: /Saiba mais/i });
    expect(link).toHaveAttribute('href', '/privacidade');
  });

  it('does not render when there is no user', () => {
    mockUserValue = { user: null };
    const { container } = render(<NetworkAnalyticsBanner />);
    expect(container.innerHTML).toBe('');
  });

  it('does not render when dismissed via localStorage', () => {
    localStorageMock.setItem('network_banner_dismissed', 'true');
    const { container } = render(<NetworkAnalyticsBanner />);
    expect(container.innerHTML).toBe('');
  });

  it('dismisses on X button click', () => {
    render(<NetworkAnalyticsBanner />);
    const closeButton = screen.getByLabelText('Fechar banner');
    fireEvent.click(closeButton);
    expect(localStorageMock.getItem('network_banner_dismissed')).toBe('true');
  });

  it('calls PATCH /v1/profile on activate click', async () => {
    const mockFetch = global.fetch as jest.Mock;
    mockFetch.mockResolvedValueOnce({ ok: true });

    render(<NetworkAnalyticsBanner />);
    const activateButton = screen.getByRole('button', { name: /Ativar contribuicao/i });
    fireEvent.click(activateButton);

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith('/v1/profile', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ allow_network_analytics: true }),
      });
    });
  });

  it('does not render when user already decided (allow_network_analytics=true)', () => {
    mockUserValue = { user: { ...mockUser, allow_network_analytics: true } };
    const { container } = render(<NetworkAnalyticsBanner />);
    expect(container.innerHTML).toBe('');
  });

  it('does not render when user already decided (allow_network_analytics=false)', () => {
    mockUserValue = { user: { ...mockUser, allow_network_analytics: false } };
    const { container } = render(<NetworkAnalyticsBanner />);
    expect(container.innerHTML).toBe('');
  });
});
