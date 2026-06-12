import React from 'react';
import { render, screen } from '@testing-library/react';
import NetworkAnalyticsSection from '../../app/privacidade/components/NetworkAnalyticsSection';

describe('NetworkAnalyticsSection', () => {
  it('renders the section title', () => {
    render(<NetworkAnalyticsSection />);
    expect(
      screen.getByText('Dados de Uso Agregados (Network Analytics)')
    ).toBeInTheDocument();
  });

  it('describes what is collected', () => {
    render(<NetworkAnalyticsSection />);
    expect(
      screen.getByText(/tipo de evento/i)
    ).toBeInTheDocument();
  });

  it('mentions what is NOT collected', () => {
    render(<NetworkAnalyticsSection />);
    expect(
      screen.getByText(/CNPJ|CPF|nome|email/i)
    ).toBeInTheDocument();
  });

  it('cites LGPD legal basis', () => {
    render(<NetworkAnalyticsSection />);
    expect(
      screen.getByText(/Art. 7, I/i)
    ).toBeInTheDocument();
  });

  it('has a link to configuracoes/privacidade', () => {
    render(<NetworkAnalyticsSection />);
    const link = screen.getByRole('link', { name: /configuracoes.*privacidade/i });
    expect(link).toHaveAttribute('href', '/configuracoes#privacidade');
  });

  it('specifies retention periods', () => {
    render(<NetworkAnalyticsSection />);
    expect(screen.getByText(/365 dias/i)).toBeInTheDocument();
    expect(screen.getByText(/730 dias/i)).toBeInTheDocument();
  });

  it('is wrapped in a semantic section', () => {
    const { container } = render(<NetworkAnalyticsSection />);
    const section = container.querySelector('section');
    expect(section).toBeInTheDocument();
  });
});
