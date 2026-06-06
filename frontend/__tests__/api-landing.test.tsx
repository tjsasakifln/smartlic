import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

/**
 * Tests for API-SELF-005: /api landing page + pricing cards.
 */

// Mock Next.js Link
jest.mock('next/link', () => {
  return function MockLink({ children, href, ...props }: any) {
    return <a href={href} {...props}>{children}</a>;
  };
});

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({ push: jest.fn(), replace: jest.fn() }),
  usePathname: () => '/api',
}));

// Mock LandingNavbar and Footer (heavy components with their own dependencies)
jest.mock('../app/components/landing/LandingNavbar', () => ({
  __esModule: true,
  default: () => <nav data-testid="landing-navbar">Navbar</nav>,
}));

jest.mock('../app/components/Footer', () => ({
  __esModule: true,
  default: () => <footer data-testid="footer">Footer</footer>,
}));

import ApiLandingPage from '../app/api/page';

describe('API Landing Page (API-SELF-005)', () => {
  it('renders the hero section with title', () => {
    render(<ApiLandingPage />);
    expect(screen.getByText(/Dados de Licitações/i)).toBeInTheDocument();
    expect(screen.getByText(/via API/i)).toBeInTheDocument();
  });

  it('renders all three pricing tiers', () => {
    render(<ApiLandingPage />);
    // Tier names appear in both pricing cards and rate limit section
    // Use getAllByText since these strings appear multiple times
    expect(screen.getAllByText('Starter').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Pro').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Scale').length).toBeGreaterThanOrEqual(1);
  });

  it('renders documentation CTA links', () => {
    render(<ApiLandingPage />);
    const docLinks = screen.getAllByText(/Documentação/i);
    expect(docLinks.length).toBeGreaterThan(0);
  });

  it('renders the quickstart steps', () => {
    render(<ApiLandingPage />);
    expect(screen.getByText('Crie sua chave')).toBeInTheDocument();
    expect(screen.getByText('Autentique')).toBeInTheDocument();
    expect(screen.getByText('Faça a chamada')).toBeInTheDocument();
  });

  it('renders landing navbar and footer', () => {
    render(<ApiLandingPage />);
    expect(screen.getByTestId('landing-navbar')).toBeInTheDocument();
    expect(screen.getByTestId('footer')).toBeInTheDocument();
  });

  it('renders rate limit section with tier info', () => {
    render(<ApiLandingPage />);
    expect(screen.getByText('Autenticação e Rate Limits')).toBeInTheDocument();
    expect(screen.getByText('Autenticação')).toBeInTheDocument();
    expect(screen.getByText('Rate Limiting')).toBeInTheDocument();
    expect(screen.getByText('Formato de Resposta')).toBeInTheDocument();
  });
});
