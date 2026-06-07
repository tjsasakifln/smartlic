/**
 * Tests for SimuladorOportunidades component (#1400).
 *
 * CONV-003-1: Interactive widget that simulates bidding opportunities
 * for a visitor's sector, embeddable in blog and SEO pages.
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { SimuladorOportunidades } from '@/app/components/conversion/SimuladorOportunidades';
import '@testing-library/jest-dom';

// Mock scrollIntoView (used by CustomSelect dropdown)
Element.prototype.scrollIntoView = jest.fn();

// Mock Next.js Link
jest.mock('next/link', () => {
  return ({ children, href, onClick, ...rest }: { children: React.ReactNode; href: string; onClick?: () => void; [key: string]: unknown }) => {
    return (
      <a href={href} onClick={onClick} {...rest}>
        {children}
      </a>
    );
  };
});

/**
 * Helper: open sector dropdown and select an option by matching label text.
 */
function selectSector(label: string) {
  const combos = screen.getAllByRole('combobox');
  fireEvent.click(combos[0]);
  const option = screen.getByRole('option', { name: label });
  fireEvent.click(option);
}

/**
 * Helper: open UF dropdown and select an option by full label text.
 */
function selectUf(label: string) {
  const combos = screen.getAllByRole('combobox');
  fireEvent.click(combos[1]);
  const option = screen.getByRole('option', { name: label });
  fireEvent.click(option);
}

describe('SimuladorOportunidades', () => {
  const originalMixpanel = (window as unknown as { mixpanel?: unknown }).mixpanel;

  afterEach(() => {
    (window as unknown as { mixpanel?: unknown }).mixpanel = originalMixpanel;
  });

  // -----------------------------------------------------------------------
  // Rendering
  // -----------------------------------------------------------------------

  it('renders the component with header and form', () => {
    render(<SimuladorOportunidades />);

    expect(screen.getByText('Simulador de Oportunidades')).toBeInTheDocument();
    expect(
      screen.getByText('Descubra quantos editais seu setor tem abertos no Brasil'),
    ).toBeInTheDocument();
    expect(screen.getByText('Setor')).toBeInTheDocument();
    expect(screen.getByText('UF')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: /Simular oportunidades/i }),
    ).toBeInTheDocument();
  });

  it('disables the simulate button when form is incomplete', () => {
    render(<SimuladorOportunidades />);

    const button = screen.getByTestId('simulador-simular-btn');
    expect(button).toBeDisabled();
  });

  it('has correct data-testid on the root element', () => {
    render(<SimuladorOportunidades />);
    expect(screen.getByTestId('simulador-oportunidades')).toBeInTheDocument();
  });

  it('accepts defaultSector and defaultUf props', () => {
    render(
      <SimuladorOportunidades
        defaultSector="software"
        defaultUf="SP"
        sourcePage="/blog/test-page"
      />,
    );

    expect(screen.getByTestId('simulador-oportunidades')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // Form interaction
  // -----------------------------------------------------------------------

  it('enables simulate button when both selectors have values', () => {
    render(<SimuladorOportunidades />);

    const button = screen.getByTestId('simulador-simular-btn');
    expect(button).toBeDisabled();

    selectSector('Alimentos e Merenda');
    expect(button).toBeDisabled();

    selectUf('São Paulo (SP)');
    expect(button).not.toBeDisabled();
  });

  // -----------------------------------------------------------------------
  // Simulation flow
  // -----------------------------------------------------------------------

  it('shows loading state after clicking simulate', () => {
    render(<SimuladorOportunidades />);

    selectSector('Hardware e Equipamentos de TI');
    selectUf('São Paulo (SP)');
    fireEvent.click(screen.getByTestId('simulador-simular-btn'));

    expect(screen.getByTestId('simulador-loading')).toBeInTheDocument();
  });

  it('shows results after simulation completes', async () => {
    render(<SimuladorOportunidades />);

    selectSector('Hardware e Equipamentos de TI');
    selectUf('São Paulo (SP)');

    fireEvent.click(screen.getByTestId('simulador-simular-btn'));

    await waitFor(
      () => {
        expect(screen.getByTestId('simulador-results')).toBeInTheDocument();
      },
      { timeout: 5000 },
    );

    expect(screen.getByText(/editais encontrados em/i)).toBeInTheDocument();
    expect(screen.getByTestId('simulador-cta-buscar')).toBeInTheDocument();
    expect(screen.getByTestId('simulador-cta-email')).toBeInTheDocument();
  }, 10000);

  // -----------------------------------------------------------------------
  // Tracking
  // -----------------------------------------------------------------------

  it('tracks simulator_started when simulate is clicked', () => {
    const trackSpy = jest.fn();
    (window as unknown as { mixpanel: { track: jest.Mock } }).mixpanel = {
      track: trackSpy,
    };

    render(<SimuladorOportunidades sourcePage="/blog/test" />);

    selectSector('Desenvolvimento de Software e Consultoria de TI');
    selectUf('Rio de Janeiro (RJ)');
    fireEvent.click(screen.getByTestId('simulador-simular-btn'));

    expect(trackSpy).toHaveBeenCalledWith('simulator_started', {
      setor: 'software',
      uf: 'RJ',
      source_page: '/blog/test',
    });
  });

  it('tracks simulator_completed after simulation finishes', async () => {
    const trackSpy = jest.fn();
    (window as unknown as { mixpanel: { track: jest.Mock } }).mixpanel = {
      track: trackSpy,
    };

    render(<SimuladorOportunidades sourcePage="/blog/test" />);

    selectSector('Vestuário e Uniformes');
    selectUf('Minas Gerais (MG)');

    fireEvent.click(screen.getByTestId('simulador-simular-btn'));

    await waitFor(
      () => {
        expect(trackSpy).toHaveBeenCalledWith(
          'simulator_completed',
          expect.objectContaining({
            setor: 'vestuario',
            uf: 'MG',
            source_page: '/blog/test',
          }),
        );
      },
      { timeout: 5000 },
    );

    const completedCall = trackSpy.mock.calls.find(
      (c: string[]) => c[0] === 'simulator_completed',
    );
    expect(completedCall).toBeDefined();
    expect(completedCall[1]).toHaveProperty('count');
    expect(completedCall[1]).toHaveProperty('total_value');
  }, 10000);

  it('tracks simulator_cta_clicked when CTA is clicked', async () => {
    const trackSpy = jest.fn();
    (window as unknown as { mixpanel: { track: jest.Mock } }).mixpanel = {
      track: trackSpy,
    };

    render(<SimuladorOportunidades />);

    selectSector('Produtos de Limpeza e Higienização');
    selectUf('Bahia (BA)');

    fireEvent.click(screen.getByTestId('simulador-simular-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('simulador-cta-buscar')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId('simulador-cta-buscar'));

    expect(trackSpy).toHaveBeenCalledWith('simulator_cta_clicked', {
      cta_type: 'buscar',
      setor: 'limpeza',
      uf: 'BA',
      source_page: 'unknown',
    });
  }, 10000);

  // -----------------------------------------------------------------------
  // Error / Edge cases
  // -----------------------------------------------------------------------

  it('does not throw when window.mixpanel is undefined', () => {
    delete (window as unknown as { mixpanel?: unknown }).mixpanel;

    render(<SimuladorOportunidades />);

    selectSector('Papelaria e Material de Escritório');
    selectUf('Paraná (PR)');

    expect(() => {
      fireEvent.click(screen.getByTestId('simulador-simular-btn'));
    }).not.toThrow();
  });

  it('shows various sector options in the dropdown', () => {
    render(<SimuladorOportunidades />);

    const sectorButton = screen.getByRole('combobox', { name: /Setor/i });
    fireEvent.click(sectorButton);

    const options = screen.getAllByRole('option');
    expect(options.some((o) => o.textContent?.includes('Vestuário'))).toBe(true);
    expect(options.some((o) => o.textContent?.includes('Medicamentos'))).toBe(true);
    expect(options.some((o) => o.textContent?.includes('Frota'))).toBe(true);
  });

  it('clears results when sector changes', async () => {
    render(<SimuladorOportunidades />);

    selectSector('Hardware e Equipamentos de TI');
    selectUf('São Paulo (SP)');

    fireEvent.click(screen.getByTestId('simulador-simular-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('simulador-results')).toBeInTheDocument();
    });

    // Change sector — results should clear
    selectSector('Alimentos e Merenda');

    expect(screen.queryByTestId('simulador-results')).not.toBeInTheDocument();
  }, 10000);

  // -----------------------------------------------------------------------
  // CTA links
  // -----------------------------------------------------------------------

  it('builds correct buscar URL for the CTA', async () => {
    render(<SimuladorOportunidades />);

    selectSector('Alimentos e Merenda');
    selectUf('Ceará (CE)');

    fireEvent.click(screen.getByTestId('simulador-simular-btn'));

    await waitFor(() => {
      expect(screen.getByTestId('simulador-cta-buscar')).toBeInTheDocument();
    });

    const link = screen.getByTestId('simulador-cta-buscar');
    expect(link).toHaveAttribute('href', '/buscar?setor=alimentos&uf=CE');
  }, 10000);
});
